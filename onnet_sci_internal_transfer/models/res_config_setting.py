from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    internal_transfer_account = fields.Many2one('account.account', string=_('Phải thu điều chuyển nội bộ'))
    x_internal_payable_account_id = fields.Many2one('account.account', 'Tài khoản phải trả nội bộ',
                                                    related='company_id.x_internal_payable_account_id', readonly=False)
    x_journal_internal_id = fields.Many2one('account.journal', string='Sổ nhật ký tài khoản nội bộ')