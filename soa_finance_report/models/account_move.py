# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('analytic_distribution')
    def _inverse_analytic_distribution(self):
        for line in self:
            if line.analytic_distribution:
                to_sync_move_line = line.move_id.line_ids.filtered(lambda l: not l.analytic_distribution)
                to_sync_move_line.analytic_distribution = line.analytic_distribution
        super()._inverse_analytic_distribution()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(AccountMoveLine, self).create(vals_list)
        for line in lines:
            has_analytic_distribution_lines = line.move_id.line_ids.filtered(lambda ml: ml.analytic_distribution)
            if not line.analytic_distribution and has_analytic_distribution_lines:
                line.analytic_distribution = has_analytic_distribution_lines[-1].analytic_distribution
        return lines

    def _get_query_currency_table(self, company_ids, currency_id, conversion_date):
        companies = self.env['res.company'].browse(company_ids)
        user_company = self.env.company
        currency_model = self.env['res.currency']
        currency_rates = currency_model.search([('active', '=', True)])._get_rates(user_company, conversion_date)
        conversion_rates = []
        for company in companies:
            conversion_rates.extend((
                company.id,
                currency_rates[currency_id.id] / currency_rates[company.currency_id.id],
                currency_id.decimal_places,
            ))
        query = '(VALUES %s) AS currency_table(company_id, rate, precision)' % ','.join(
            '(%s, %s, %s)' for i in companies)
        return self.env.cr.mogrify(query, conversion_rates).decode(self.env.cr.connection.encoding)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _default_financial_currency(self):
        currency_id = self.env.ref('base.USD')
        cf_currency = self.env['ir.config_parameter'].sudo().get_param('soa_finance_report.cf_currency_id', False)
        if cf_currency:
            currency_id = self.env['res.currency'].sudo().browse(int(cf_currency))
        return currency_id

    financial_currency_id = fields.Many2one('res.currency', string='Financial Currency',
                                            default=_default_financial_currency)

    amount_financial_currency = fields.Monetary(string='Planned Amount in Financial Report', store=True, precompute=True,
                                                currency_field='financial_currency_id', compute='_compute_amount_financial_currency')

    amount_paid = fields.Monetary(store=True)

    actual_amount_financial_currency = fields.Monetary(string='Amount paid in Financial Report', store=True, precompute=True,
                                                currency_field='financial_currency_id', compute='_compute_actual_amount_financial_currency')

    sale_order_count = fields.Integer(store=True, precompute=True)
    purchase_order_count = fields.Integer(store=True, precompute=True)

    analytic_account_id = fields.Many2one('account.analytic.account', store=True, compute_sudo=True,
                                          string="Project Analytic Account", compute="_compute_analytic")
    analytic_plan_id = fields.Many2one('account.analytic.plan', string="Analytic Plan",
                                       store=True, compute_sudo=True, compute="_compute_analytic")

    @api.depends('line_ids', 'line_ids.analytic_distribution')
    def _compute_analytic(self):
        for item in self:
            analytic_account_id = False
            analytic_plan_id = False
            lines = item.line_ids.filtered(lambda l: l.analytic_distribution)
            if lines:
                analytic_distribution_keys = list(lines[0].analytic_distribution.keys())
                analytic_distribution_key = analytic_distribution_keys[0].split(',')[0]
                try:
                    analytic_account = self.env['account.analytic.account'].browse(int(analytic_distribution_key))
                    analytic_plan = analytic_account.plan_id
                    analytic_account_id = analytic_account.id if analytic_account else False
                    analytic_plan_id = analytic_plan.id if analytic_plan else False
                except:
                    analytic_account_id = False
                    analytic_plan_id = False

            item.analytic_account_id = analytic_account_id
            item.analytic_plan_id = analytic_plan_id

    @api.depends('amount_total_in_currency_signed', 'currency_id', 'financial_currency_id')
    def _compute_amount_financial_currency(self):
        for item in self:
            item.amount_financial_currency = 0
            amount_financial_currency = item.currency_id._convert(
                item.amount_total_in_currency_signed, item.financial_currency_id)
            item.amount_financial_currency = amount_financial_currency

    @api.depends('transaction_ids', 'transaction_ids.state', 'transaction_ids.amount')
    def _compute_amount_paid(self):
        """ Sum all the transaction amount for which state is in 'authorized' or 'done'
        """
        for invoice in self:
            invoice.amount_paid = sum(
                invoice.transaction_ids.filtered(
                    lambda tx: tx.state in ('authorized', 'done')
                ).mapped('amount')
            )

    @api.depends('amount_total_signed', 'amount_residual_signed', 'company_currency_id', 'financial_currency_id')
    def _compute_actual_amount_financial_currency(self):
        for item in self:
            item.actual_amount_financial_currency = 0
            actual_amount = abs(item.amount_total_signed) - abs(item.amount_residual_signed)
            actual_amount_financial_currency = item.company_currency_id._convert(
                actual_amount, item.financial_currency_id)
            item.actual_amount_financial_currency = actual_amount_financial_currency

    @api.depends('line_ids', 'line_ids.sale_line_ids')
    def _compute_origin_so_count(self):
        for move in self:
            move.sale_order_count = len(move.line_ids.sale_line_ids.order_id)

    @api.depends('line_ids', 'line_ids.purchase_line_id')
    def _compute_origin_po_count(self):
        for move in self:
            move.purchase_order_count = len(move.line_ids.purchase_line_id.order_id)
