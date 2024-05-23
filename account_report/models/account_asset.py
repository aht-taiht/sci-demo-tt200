from odoo import fields, models


class AccountAsset(models.Model):
    _inherit = "account.asset"

    x_code = fields.Text(string='Mã chi phí trả trước')