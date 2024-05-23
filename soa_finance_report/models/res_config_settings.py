# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cf_currency_id = fields.Many2one('res.currency', string='Cashflow Currency')

    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('soa_finance_report.cf_currency_id', self.cf_currency_id.id)
        return res

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        with_user = self.env['ir.config_parameter'].sudo()
        cf_currency_id = with_user.get_param('soa_finance_report.cf_currency_id')
        res.update(cf_currency_id=int(cf_currency_id) if cf_currency_id else False, )

        return res
