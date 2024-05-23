# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    def _default_financial_currency(self):
        currency_id = self.env.ref('base.USD')
        cf_currency = self.env['ir.config_parameter'].sudo().get_param('soa_finance_report.cf_currency_id', False)
        if cf_currency:
            currency_id = self.env['res.currency'].sudo().browse(int(cf_currency))
        return currency_id

    cf_currency_id = fields.Many2one(
        'res.currency', 'Cashflow Currency', readonly=True, default=_default_financial_currency)
    currency_amount = fields.Monetary(
        'Amount in Currency', currency_field='cf_currency_id', compute='_compute_amount_currency', store=True)

    @api.depends('cf_currency_id', 'date', 'amount')
    def _compute_amount_currency(self):
        for line in self:
            line.currency_amount = 0.0
            currency_amount = self.company_id.currency_id._convert(
                line.amount, line.cf_currency_id, company=line.company_id, date=line.date)
            line.currency_amount = currency_amount
