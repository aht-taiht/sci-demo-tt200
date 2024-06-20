from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError
from .account_account_type import TYPE


class AccountTypeMapping(models.Model):
    _name = 'account.type.mapping'

    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence')
    # account_type_ids = fields.Many2many('account.account.type',
    #     'account_account_type_account_type_mapping_rel', 'mapping_id', 'type_id', string='Account Type')
    type_1 = type = fields.Selection(TYPE, string='Loại 1')
    type_2 = type = fields.Selection(TYPE, string='Loại 2')
