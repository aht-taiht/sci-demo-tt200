from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError


class AccountTypeMapping(models.Model):
    _name = 'account.type.mapping'

    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence')
    account_type_ids = fields.Many2many('account.account.type', string='Account Type')
