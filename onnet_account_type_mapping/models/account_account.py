from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError

class AccountAccount(models.Model):
    _name = 'account.account'

    user_type_id = fields.Many2one('account.account.type', string='Type', required=True)
    type = fields.Selection(related='user_type_id.type', string='Loại gốc', readonly=True)