from odoo import models, fields, _


class AccountAccount(models.Model):
    _inherit = 'account.account'

    compacted = fields.Boolean('Compacte entries.', help='If flagged, no details will be displayed in the Standard report, only compacted amounts.', default=False)
    type_third_parties = fields.Selection([('no', 'No'), ('supplier', 'Supplier'), ('customer', 'Customer')], string='Third Partie', required=True, default='no')

class AccountAccountType(models.Model):
    _name = "account.account.type"
    _inherit = ['account.account.type', 'synced.mixin']

    type = fields.Selection([
        ('other', 'Regular'),
        ('receivable', 'Receivable'),
        ('payable', 'Payable'),
        ('liquidity', 'Liquidity'),
        ('regular', 'Regular')
    ], required=True, default='other',
        help="The 'Internal Type' is used for features available on " \
             "different types of accounts: liquidity type is for cash or bank accounts" \
             ", payable/receivable is for vendor/customer accounts.")
    internal_group = fields.Selection([
        ('equity', 'Equity'),
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('off_balance', 'Off Balance'),
        ('Xác định KQKD', 'Xác định KQKD')
    ], string="Internal Group",
        required=True,
        help="The 'Internal Group' is used to filter accounts based on the internal group set on the account type.")

class AccountAsset(models.Model):
    _inherit = "account.asset"

    asset_uom = fields.Selection([
        ('kit', _('Bộ')),
        ('units', _('Cái')),], string= _('Đơn vị'))