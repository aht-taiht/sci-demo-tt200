from odoo import models, fields, _


class AccountAccount(models.Model):
    _inherit = 'account.account'

    compacted = fields.Boolean('Compacte entries.', help='If flagged, no details will be displayed in the Standard report, only compacted amounts.', default=False)
    type_third_parties = fields.Selection([('no', 'No'), ('supplier', 'Supplier'), ('customer', 'Customer')], string='Third Partie', required=True, default='no')

class AccountAsset(models.Model):
    _inherit = "account.asset"

    asset_uom = fields.Selection([
        ('kit', _('Bộ')),
        ('units', _('Cái')),], string= _('Đơn vị'))
