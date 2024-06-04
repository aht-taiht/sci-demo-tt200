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
        # query = f"""
        #     select a.account_account_type_id
        #     from account_account_type_account_type_mapping_rel as a left join (
        #         select *
        #         from account_account_type_account_type_mapping_rel
        #         where account_account_type_id = {account_type}
        #     ) as b on a.account_type_mapping_id = b.account_type_mapping_id
        #     where b.account_type_mapping_id is not Null
        #     and a.account_account_type_id != {account_type}
        #
        # """
        query = f"""
            SELECT id FROM account_account_type 
            WHERE type in (SELECT type_1 FROM account_type_mapping WHERE type_2 == {account_type})
            OR  type in (SELECT type_2 FROM account_type_mapping WHERE type_1 == {account_type})
        """

        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()
        _logger.info(str(data))
        return data

    @api.depends('account_id', 'move_id.line_ids', 'debit', 'credit')
    def _compute_offset_account(self):
        date_compute = datetime.today() - relativedelta(months=2)
        for line in self.filtered(lambda x: x.date.strftime('%Y-%m-%d') >= date_compute.strftime('%Y-%m-%d')):
            try:
                # line.offset_account_ids = line._get_offset_account(line)
                # line.offset_account = get_string_offset_account(
                #     line.offset_account_ids.mapped('code')) if line.offset_account_ids else ""
                account_ids = line._get_offset_account(line)
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
        selected_ids = self.env.context.get('active_ids', [])
        selected_lines = self.env['account.move.line'].browse(selected_ids)
        for line in selected_lines:
            if not line.offset_account_ids:
                line.offset_account_ids = line._get_offset_account(line)
                line.offset_account = get_string_offset_account(line.offset_account_ids.mapped('code')) if line.offset_account_ids else ""

    def _get_offset_account(self, line):
        offset_accounts = []
        if line.move_id.is_invoice(True) and line.balance != 0 and line.account_id:
            # get account type have same mapping
            account_type_list = self.get_data(line.account_id.type)
            account_type = [rec['account_account_type_id'] for rec in account_type_list]
            offset_lines = line.move_id.line_ids.filtered(lambda x:
                                                          abs(x.balance * line.balance) != x.balance * line.balance
                                                          and x.account_id.user_type_id.id in account_type
                                                          )
            offset_accounts = offset_lines.mapped('account_id').ids
        elif line.move_id.move_type == 'entry' and line.balance != 0 and line.account_id:
            offset_lines = line.move_id.line_ids.filtered(lambda x:
                                                          abs(x.balance * line.balance) != x.balance * line.balance
                                                          )
            offset_accounts = offset_lines.mapped('account_id').ids

        return offset_accounts
