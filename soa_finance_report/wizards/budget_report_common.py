# -*- coding: utf-8 -*-
import io
import re
from datetime import datetime, date

import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import expr_eval

ACCOUNT_CODES_ENGINE_SPLIT_REGEX = re.compile(r"(?=[+-])")


def get_years():
    year_list = [str(num) for num in range(datetime.now().year - 20, datetime.now().year + 2)]
    year_list = sorted(year_list, reverse=True)
    return [(element, element) for element in year_list]


class BudgetReportCommon(models.AbstractModel):
    _name = 'budget.combined.common'
    _description = 'Budget Report Common'

    date_from = fields.Date()
    date_to = fields.Date()
    year = fields.Selection(get_years(), string='Year')
    analytic_plan_ids = fields.Many2many('account.analytic.plan')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many('res.company', string='Companies')

    @api.model
    def default_get(self, fields_list):
        res = super(BudgetReportCommon, self).default_get(fields_list)
        starting_day_of_current_year = datetime.now().date().replace(month=1, day=1)
        ending_day_of_current_year = datetime.now().date().replace(month=12, day=31)
        res['year'] = str(datetime.now().year)
        res['date_from'] = starting_day_of_current_year
        res['date_to'] = ending_day_of_current_year
        return res

    @api.constrains('date_from', 'date_to', 'analytic_plan_ids')
    def check_constrains_fields(self):
        for wizard in self:
            if not wizard.date_from or not wizard.date_to:
                raise UserError(_('Date From and Date to must be required !'))
            if not wizard.analytic_plan_ids:
                raise UserError(_('You must select one analytic plan at least !'))

    def _check_date_time_range(self):
        if self.date_from and self.date_to and self.date_from.year != self.date_to.year:
            raise ValidationError(_('You can only view the report with in the same year !'))

    @api.onchange('date_from', 'date_to')
    def _onchange_from_date_to(self):
        if self.date_from and self.date_to:
            self._check_date_time_range()
            if self.date_from > self.date_to:
                raise ValidationError(_('From date must be less than To date !'))

    @api.onchange('year')
    def _onchange_year(self):
        if self.year:
            self.date_from = datetime(year=int(self.year), month=1, day=1)
            self.date_to = datetime(year=int(self.year), month=12, day=31)

    def _get_currency_rates(self):
        user_company = self.company_id
        currency_model = self.env['res.currency']
        conversion_date = self.date_to.strftime('%Y-%m-%d')
        currency_rates = currency_model.search([('active', '=', True)])._get_rates(user_company, conversion_date)
        return currency_rates

    def _get_report_name(self):
        return _('Budget Report')

    def _get_start_days(self):
        start_days = []
        current_date = self.date_from.replace(day=1)
        while current_date <= self.date_to:
            start_days.append(current_date)
            current_date += relativedelta(months=1)
        return start_days

    def _get_start_days_12_months(self):
        year_from = self.date_from.year
        year_to = self.date_to.year
        start_days = [date(year_from, month, 1) for month in range(1, 13)]
        if year_to != year_from:
            start_days += [date(year_to, month, 1) for month in range(1, 13)]
        return start_days

    def get_period_info(self):
        return f'Period: {self.date_from.strftime("%Y-%m-%d")} - {self.date_to.strftime("%Y-%m-%d")}'

    def get_analytic_plans(self):
        return f'BU: {", ".join(self.analytic_plan_ids.mapped("name"))}'

    def _get_header_colums(self):
        return []

    def _inject_report_into_xlsx_sheet(self, workbooks, sheet):
        """"""

    def get_xlsx(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })

        self._inject_report_into_xlsx_sheet(workbook, workbook.add_worksheet(self._get_report_name()))

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        # Debug block code
        # with open("output.xlsx", "wb") as f:
        #     f.write(generated_file)
        output.close()
        return {
            'file_name': f'{self._get_report_name()}.xlsx',
            'file_content': generated_file,
            'file_type': 'xlsx',
        }

    def action_export_to_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/download/xlsx/%s/%s/%s' % (
                'BudgetCombinedReport', self._name, self.id)
        }
