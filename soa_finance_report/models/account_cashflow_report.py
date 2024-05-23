# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from dateutil.relativedelta import relativedelta


class AccountCashflowReport(models.Model):
    _name = 'account.cashflow.report'
    _description = 'Account Cashflow Report'
    _order = 'schedule_date desc'
    _auto = False

    cf_plan_id = fields.Many2one('account.cashflow.forecast', string="CF Plan", readonly=True)
    account_move_id = fields.Many2one('account.move', string="Invoice/Bill", readonly=True)
    ref = fields.Char(string="Reference", readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Project Analytic Account", readonly=True)
    # Related analytic_account_id.analytic_plan_id
    analytic_plan_id = fields.Many2one('account.analytic.plan', string="Analytic Plan", readonly=True)
    schedule_date = fields.Date(string="Schedule Date", readonly=True)

    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', readonly=True)
    financial_currency_id = fields.Many2one('res.currency', string='Financial Currency', readonly=True)

    amount = fields.Monetary(string="Planned Amount", currency_field='company_currency_id', readonly=True)
    amount_currency = fields.Monetary(string="Planned Amount in Currency", currency_field='currency_id', readonly=True)
    amount_financial_currency = fields.Monetary(
        string="Planned Amount in Financial Currency", currency_field='financial_currency_id', readonly=True)

    actual_amount = fields.Monetary(string="Actual Amount", currency_field='company_currency_id', readonly=True)
    actual_amount_currenry = fields.Monetary(string="Actual Amount in Currency",
                                             currency_field='currency_id', readonly=True)
    actual_amount_financial_currency = fields.Monetary(
        string="Actual Amount in Financial Currency", currency_field='financial_currency_id', readonly=True)
    # amount_financial_currency - actual_amount_financial_currency
    residual_amount_finanicla_currency = fields.Monetary(
        string="Residual Amount", currency_field='financial_currency_id', readonly=True)
    # cf_plan_id.description
    description = fields.Text(string="Description", readonly=True)
    # cf_plan_id.note
    note = fields.Text(string="Note", readonly=True)

    def action_confirm_scrolling_up(self):
        message = "Are you sure to scrolling up all schedule date to next month?"
        wizard_id = self.env['confirm.wizard'].create({
            'message': message,
            'res_model': self._name,
            'active_ids': str(self.ids),
            'method': '_scrolling_up_schedule_date'
        })
        return {
            'name': _('Successfull'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'confirm.wizard',
            # pass the id
            'res_id': wizard_id.id,
            'target': 'new'
        }

    def _scrolling_up_schedule_date(self, active_ids):
        records = self.browse(active_ids)
        plan_records = records.filtered(lambda r: r.cf_plan_id)
        move_records = records.filtered(lambda r: r.account_move_id)

        for record in records:
            current_schedule_date = record.schedule_date
            next_schedule_date = current_schedule_date + relativedelta(months=1)
            if record.cf_plan_id:
                # record.cf_plan_id.write({'schedule_date': next_schedule_date})
                cf_plan_id = record.cf_plan_id
                cf_company_currency_id = cf_plan_id.company_currency_id
                cf_currency_id = cf_plan_id.currency_id
                cf_amount_currency = cf_plan_id.amount_currency
                cf_actual_amount = cf_plan_id.actual_amount
                cf_actual_amount_currency = cf_company_currency_id._convert(cf_actual_amount, cf_currency_id)

                if cf_actual_amount == 0 and cf_amount_currency != 0:
                    cf_plan_id.write({'schedule_date': next_schedule_date})
                # elif (cf_amount_currency - cf_actual_amount_currency) > 0:
                elif abs(cf_amount_currency - cf_actual_amount_currency) > 0:
                    new_cf_plan = cf_plan_id.copy({
                        'schedule_date': next_schedule_date,
                        'amount_currency': cf_amount_currency - cf_actual_amount_currency
                    })
                    cf_plan_id.write({'amount_currency': cf_actual_amount_currency})

            if record.account_move_id:
                if record.actual_amount == 0 and record.amount != 0:
                    record.account_move_id.write({'invoice_date_due': next_schedule_date})

    def _query(self):
        # with_ = self._with()
        financial_currency_id = self.env.ref('base.USD').id
        cf_currency_id = self.env['ir.config_parameter'].sudo().get_param('soa_finance_report.cf_currency_id', False)
        if cf_currency_id:
            financial_currency_id = int(cf_currency_id)

        return """
            SELECT
                row_number() over (ORDER BY create_date) as id,
                cf_plan_id,
                account_move_id,
                ref,
                company_id,
                analytic_account_id,
                analytic_plan_id,
                schedule_date,
                currency_id,
                company_currency_id,
                financial_currency_id,
                amount,
                amount_currency,
                amount_financial_currency,
                actual_amount,
                actual_amount_currenry,
                actual_amount_financial_currency,
                COALESCE(amount_financial_currency - actual_amount_financial_currency) as residual_amount_finanicla_currency,
                description,
                note
            FROM (
                SELECT
                    acf.id as cf_plan_id,
                    NULL as account_move_id,
                    acf.ref as ref,
                    company.id as company_id,
                    so.analytic_account_id as analytic_account_id,
                    aa.plan_id as analytic_plan_id,
                    acf.schedule_date as schedule_date,
                    self_currency.id as currency_id,
                    company_currency.id as company_currency_id,
                    financial_currency.id as financial_currency_id,
                    acf.amount as amount,
                    acf.amount_currency as amount_currency,
                    acf.amount_financial_currency as amount_financial_currency,
                    acf.actual_amount as actual_amount,
                    acf.actual_amount_currenry as actual_amount_currenry,
                    acf.actual_amount_financial_currency as actual_amount_financial_currency,
                    acf.description as description,
                    acf.note as note,
                    acf.create_date as create_date
                FROM account_cashflow_forecast acf
                JOIN res_company company ON company.id = acf.company_id
                JOIN res_currency self_currency ON self_currency.id = acf.currency_id
                JOIN res_currency company_currency ON company_currency.id = company.currency_id
                JOIN res_currency financial_currency ON financial_currency.id = {financial_currency_id}
                JOIN sale_order so ON so.id = acf.sale_order_id
                JOIN account_analytic_account aa ON aa.id = so.analytic_account_id

                UNION ALL

                SELECT
                    NULL as cf_plan_id,
                    am.id as account_move_id,
                    am.name as ref,
                    am.company_id as company_id,
                    am.analytic_account_id as analytic_account_id,
                    am.analytic_plan_id as analytic_plan_id,
                    am.invoice_date_due as schedule_date,
                    self_currency.id as currency_id,
                    company_currency.id as company_currency_id,
                    -- am.financial_currency_id as financial_currency_id,
                    financial_currency.id as financial_currency_id,
                    am.amount_total_signed as amount,
                    am.amount_total_in_currency_signed as amount_currency,
                    am.amount_financial_currency as amount_financial_currency,
                    COALESCE(abs(am.amount_total_signed) - abs(am.amount_residual_signed), 0) as actual_amount,
                    COALESCE(
                        CASE
                            WHEN am.move_type = 'entry' THEN abs(am.amount_residual)
                            ELSE -(am.amount_residual)
                        END
                    , 0.0) AS actual_amount_currenry,
                    am.actual_amount_financial_currency as actual_amount_financial_currency,
                    am.name as description,
                    NULL as note,
                    am.create_date as create_date
                FROM account_move am
                JOIN res_company company ON company.id = am.company_id
                JOIN res_currency self_currency ON self_currency.id = am.currency_id
                JOIN res_currency company_currency ON company_currency.id = company.currency_id
                JOIN res_currency financial_currency ON financial_currency.id = {financial_currency_id}
                WHERE am.state = 'posted' AND am.move_type != 'entry' AND am.sale_order_count = 0 AND am.purchase_order_count = 0
            ) result_table

        """.format(financial_currency_id=financial_currency_id)

    @property
    def _table_query(self):
        return self._query()
