from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api
import time


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
        return data

    @api.depends('account_id', 'move_id.line_ids', 'debit', 'credit')
    def _compute_offset_account(self):
        for line in self:
            line.offset_account_ids = line._get_offset_account(line)
            line.offset_account = get_string_offset_account(
                line.offset_account_ids.mapped('code')) if line.offset_account_ids else ""

    def _set_offset_account(self):
        for line in self:
            if not line.offset_account_ids:
                line.offset_account_ids = line._get_offset_account(line)
                line.offset_account = get_string_offset_account(
                    line.offset_account_ids.mapped('code')) if line.offset_account_ids else ""

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