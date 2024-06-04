from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError

TYPE = [
    ('other', 'Thông Thường'),
    ('receivable', 'Khoản phải thu'),
    ('payable', 'Phải trả'),
    ('liquidity', 'Thanh khoản'),
    ('regular', 'Regular')
]

class AccountAccountType(models.Model):
    _name = 'account.account.type'
    _description = "Account Type"

    name = fields.Char(string='Account Type', required=True, translate=True)
    key = fields.Char(string="Key")
    type = fields.Selection(TYPE, string='Loại')