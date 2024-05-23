from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_internal_payable_account_id = fields.Many2one('account.account', 'Tài khoản phải trả nội bộ')
