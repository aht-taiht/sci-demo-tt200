from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api
import time
import logging

_logger = logging.getLogger(__name__)


def get_string_offset_account(account_codes):
    offset_account = ""
    for code in account_codes:
        offset_account += code
        if code != account_codes[-1]:
            offset_account += ", "
    return offset_account


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    offset_account_ids = fields.Many2many('account.account',
                                          # compute='_compute_offset_account',
                                          store=True,
                                          readonly=True,
                                          )

    offset_account = fields.Char(string='Offset Account Code',
                                 # compute='_compute_offset_account',
                                 store=True
                                 )

    def get_data(self, account_type):
        _logger.info(str(account_type))
        query = """
            SELECT aat.key AS account_type
            FROM account_account_type_account_type_mapping_rel AS type_mapping
            LEFT JOIN (
                SELECT * 
                FROM account_account_type_account_type_mapping_rel AS mapping_rel
                JOIN account_account_type ON account_account_type.id = mapping_rel.type_id
                WHERE account_account_type.key = '{account_type}'
            ) AS type_mapping_2 ON type_mapping.mapping_id = type_mapping_2.mapping_id
            JOIN account_account_type AS aat ON aat.id = type_mapping.type_id
            WHERE type_mapping_2.mapping_id IS NOT NULL
                AND aat.key != '{account_type}'

        """.format(account_type=account_type)
        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()
        _logger.info(str(data))
        return data

    @api.depends('account_id', 'move_id.line_ids', 'debit', 'credit')
    def _compute_offset_account(self):
        for line in self:
            try:
                # line.offset_account_ids = line._get_offset_account(line)
                # line.offset_account = get_string_offset_account(line.offset_account_ids.mapped('code')) if line.offset_account_ids else ""
                _logger.info('--------------------------------------- _compute_offset_account -------------------------------------')
                account_ids = line._get_offset_account(line)
                _logger.info(str(line.move_id.id))
                _logger.info(str(account_ids))
                self.delete_account_account_account_move_line_rel(line.id)
                for account_id in account_ids:
                    self.insert_account_account_account_move_line_rel(line.id, account_id.id)
                    self.update_account_move_line(line.id, get_string_offset_account(line.offset_account_ids.mapped('code')) if line.offset_account_ids else "")
            except Exception as e:
                
                _logger.info(str(e))
                pass

    def delete_account_account_account_move_line_rel(self, move_line_id):
        query = f"""
                    DELETE FROM account_account_account_move_line_rel WHERE account_move_line_id = {move_line_id}
                """
        self.env.cr.execute(query)
        return True

    def insert_account_account_account_move_line_rel(self, move_line_id, account_id):
        query = f"""
                INSERT INTO account_account_account_move_line_rel (account_move_line_id, account_account_id) VALUES ({move_line_id}, {account_id})
            """
        self.env.cr.execute(query)
        return True

    def update_account_move_line(self, move_line_id, offset_account):
        query = f"""
                        UPDATE account_move_line SET offset_account = {offset_account} WHERE id = {move_line_id}
                    """
        self.env.cr.execute(query)
        return True

    def _set_offset_account(self):
        for line in self:
            if not line.offset_account_ids:
                line.offset_account_ids = line._get_offset_account(line)
                line.offset_account = get_string_offset_account(line.offset_account_ids.mapped('code')) if line.offset_account_ids else ""

    def _get_offset_account(self, line):
        offset_accounts = []
        if line.move_id.is_invoice(True) and line.account_id and line.balance != 0:
            # get account type have same mapping
            account_type_list = self.get_data(line.account_id.account_type)
            account_type = [rec['account_type'] for rec in account_type_list]
            offset_lines = line.move_id.line_ids.filtered(lambda x:
                                                          abs(x.balance * line.balance) != x.balance * line.balance
                                                          and x.account_id.account_type in account_type
                                                          )
            offset_accounts = offset_lines.mapped('account_id').ids or False
        elif line.move_id.move_type == 'entry' and line.account_id and line.balance != 0:
            offset_lines = line.move_id.line_ids.filtered(lambda x:
                                                          abs(x.balance * line.balance) != x.balance * line.balance
                                                          )
            offset_accounts = offset_lines.mapped('account_id').ids or False
        return offset_accounts
