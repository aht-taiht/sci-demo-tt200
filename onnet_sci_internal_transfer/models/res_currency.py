from odoo import models, fields, _


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    internal_transfer_account = fields.Many2one('account.account', string=_('Phải thu điều chuyển nội bộ'))