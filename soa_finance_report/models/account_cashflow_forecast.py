# -*- coding: utf-8 -*-

from odoo import models, api, fields, _


class AccountCashflowForecast(models.Model):
    _name = 'account.cashflow.forecast'
    _description = 'Account Cashflow Forecast'

    def _default_financial_currency(self):
        currency_id = self.env.ref('base.USD')
        cf_currency = self.env['ir.config_parameter'].sudo().get_param('soa_finance_report.cf_currency_id', False)
        if cf_currency:
            currency_id = self.env['res.currency'].sudo().browse(int(cf_currency))
        return currency_id

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade')
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', ondelete='cascade')
    ref = fields.Char(string='Reference')
    analytic_account_id = fields.Many2one('account.analytic.account', related='sale_order_id.analytic_account_id',
                                          string='Project Analytic Account')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')
    delay_type = fields.Selection([
        ('days_after', 'Days after invoice date'),
        ('days_after_end_of_month', 'Days after end of month'),
        ('days_after_end_of_next_month', 'Days after end of next month'),
        ('days_after_etd', 'After ETD'),
        ('days_after_atd', 'After ATD'),
        ('days_after_order', 'After Order Date'),
    ], required=True, default='days_after', string='Delay Type')
    nb_days = fields.Float(string='Days')
    description = fields.Text(string='Description')
    schedule_date = fields.Date(string='Schedule Date')

    company_id = fields.Many2one('res.company', string="Company", required=True, readonly=True,
                                 default=lambda self: self.env.company)
    # currency from SO, PO
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency', precompute=True,
                                  store=True)
    amount_currency = fields.Monetary(string='Planned Amount in Currency', currency_field='currency_id')
    # currency company
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', related='company_id.currency_id',
                                          required=True)
    amount = fields.Monetary(string='Planned Amount', currency_field='company_currency_id', compute='_compute_amount',
                             store=True)
    # currency report
    financial_currency_id = fields.Many2one('res.currency', string='Financial Currency',
                                            default=_default_financial_currency)
    amount_financial_currency = fields.Monetary(string='Planned Amount in Financial Report', store=True,
                                                currency_field='financial_currency_id',
                                                compute='_compute_amount_financial_currency')
    # task 65
    actual_amount = fields.Monetary(string='Actual Amount', currency_field='company_currency_id',
                                    compute='_compute_actual_amount', store=True)
    actual_amount_currenry = fields.Monetary(string='Actual Amount in Currency', currency_field='currency_id',
                                    compute='_compute_actual_amount_currenry', store=True)
    actual_amount_financial_currency = fields.Monetary(string='Actual Amount in Financial Currency', store=True,
                                                       currency_field='financial_currency_id',
                                                       compute='_compute_actual_amount_financial')
    residual_amount_financial_currency = fields.Monetary(string='Residual Amount',
                                                         currency_field='financial_currency_id',
                                                         compute='_compute_residual_amount_financial')
    note = fields.Text(string='Note')

    @api.depends('sale_order_id', 'purchase_order_id')
    def _compute_currency(self):
        for item in self:
            currency = (item.purchase_order_id.currency_id or item.sale_order_id.currency_id)
            item.currency_id = currency

    @api.depends('amount_currency', 'currency_id', 'company_currency_id')
    def _compute_amount(self):
        for item in self:
            item.amount = 0
            amount = item.currency_id._convert(item.amount_currency, item.company_currency_id)
            item.amount = amount

    @api.depends('amount_currency', 'currency_id', 'financial_currency_id')
    def _compute_amount_financial_currency(self):
        for item in self:
            item.amount_financial_currency = 0
            amount_financial_currency = item.currency_id._convert(item.amount_currency, item.financial_currency_id)
            item.amount_financial_currency = amount_financial_currency

    @api.depends('sale_order_id',
                 'sale_order_id.account_payment_ids',
                 'sale_order_id.account_payment_ids.amount',
                 'sale_order_id.account_payment_ids.state',
                 'purchase_order_id',
                 'purchase_order_id.account_payment_ids',
                 'purchase_order_id.account_payment_ids.amount',
                 'purchase_order_id.account_payment_ids.state',
                 )
    def _compute_actual_amount(self):
        for item in self:
            # item.actual_amount = 0
            # actual amount sale
            actual_sale_amount = 0
            for sale_payment_id in item.sale_order_id.account_payment_ids.filtered(lambda i: i.state == 'posted'):
                if sale_payment_id.currency_id != item.company_currency_id:
                    exchange_sale_amount = sale_payment_id.currency_id._convert(sale_payment_id.amount,
                                                                                item.company_currency_id)
                    actual_sale_amount += exchange_sale_amount
                else:
                    actual_sale_amount += sale_payment_id.amount

            sale_cashflow_lines = item.sale_order_id.cashflow_forecast_ids.filtered(
                lambda i: not i.purchase_order_id).sorted(
                lambda x: x.schedule_date)
            if not actual_sale_amount:
                for sale_cashflow_line in sale_cashflow_lines:
                    sale_cashflow_line.actual_amount = actual_sale_amount
            else:
                for sale_cashflow_line in sale_cashflow_lines:
                    if sale_cashflow_line.amount < actual_sale_amount:
                        sale_cashflow_line.actual_amount = sale_cashflow_line.amount
                        actual_sale_amount -= sale_cashflow_line.amount
                    else:
                        sale_cashflow_line.actual_amount = actual_sale_amount
                        break

            # actual amount of purchase
            actual_purchase_amount = 0
            for purchase_payment_id in item.purchase_order_id.account_payment_ids.filtered(
                    lambda i: i.state == 'posted'):
                if purchase_payment_id.currency_id != item.company_currency_id:
                    exchange_purchase_amount = purchase_payment_id.currency_id._convert(purchase_payment_id.amount,
                                                                                        item.company_currency_id)
                    actual_purchase_amount += exchange_purchase_amount
                else:
                    actual_purchase_amount += purchase_payment_id.amount

            purchase_cashflow_lines = item.sale_order_id.cashflow_forecast_ids.filtered(
                lambda i: i.purchase_order_id and i.purchase_order_id == item.purchase_order_id).sorted(
                lambda x: x.schedule_date)
            if not actual_purchase_amount:
                for purchase_cashflow_line in purchase_cashflow_lines:
                    purchase_cashflow_line.actual_amount = actual_purchase_amount
            else:
                for purchase_cashflow_line in purchase_cashflow_lines:
                    if abs(purchase_cashflow_line.amount) < actual_purchase_amount:
                        purchase_cashflow_line.actual_amount = purchase_cashflow_line.amount
                        actual_purchase_amount += purchase_cashflow_line.amount
                    else:
                        purchase_cashflow_line.actual_amount = -actual_purchase_amount
                        break

    @api.depends('actual_amount', 'company_currency_id', 'currency_id')
    def _compute_actual_amount_currenry(self):
        for item in self:
            actual_amount_currenry = item.company_currency_id._convert(item.actual_amount, item.currency_id)
            item.actual_amount_currenry = actual_amount_currenry

    @api.depends('actual_amount', 'company_currency_id', 'financial_currency_id')
    def _compute_actual_amount_financial(self):
        for item in self:
            actual_amount_financial_currency = item.company_currency_id._convert(item.actual_amount,
                                                                                 item.financial_currency_id)
            item.actual_amount_financial_currency = actual_amount_financial_currency

    @api.depends('amount_financial_currency', 'actual_amount_financial_currency')
    def _compute_residual_amount_financial(self):
        for item in self:
            item.residual_amount_financial_currency = 0
            residual_amount_financial_currency = item.amount_financial_currency - item.actual_amount_financial_currency
            item.residual_amount_financial_currency = residual_amount_financial_currency
