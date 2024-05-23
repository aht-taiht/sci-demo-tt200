# -*- coding: utf-8 -*-
import io
import re
from collections import defaultdict
from datetime import datetime, date
import keyword

import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import expr_eval

from odoo.addons.soa_finance_report.wizards.budget_report_common import ACCOUNT_CODES_ENGINE_SPLIT_REGEX

import logging
_logger = logging.getLogger(__name__)


class FinancialReportSummary(models.TransientModel):
    _name = 'soa.financial.report.summary'
    _inherit = 'budget.combined.common'

    @api.constrains('date_from', 'date_to', 'analytic_plan_ids')
    def check_constrains_fields(self):
        for wizard in self:
            if not wizard.date_from or not wizard.date_to:
                raise UserError(_('Date From and Date to must be required !'))

    def _get_report_name(self):
        return _('Financial Reports Summary')

    def get_xlsx(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })
        project_plan, _other_plans = self.env['account.analytic.plan']._get_all_plans()
        all_plans = (project_plan + _other_plans)
        default_wizard_values = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'year': self.year,
            'company_id': self.company_id.id,
            'company_ids': self.env.company.search([]).ids
        }
        report_models = [
            'budget.combined.report.wizard',
            'budget.reforecast.combined.report',
            'soa.profit.and.loss.combined.report',
            'profit.and.loss.bu.allocation.report',
            'soa.profit.and.loss.report',
            'soa.fs.combined.pl.report',
            'soa.fs.combined.bs.report',
        ]
        for report_model in report_models:
            if report_model == 'profit.and.loss.bu.allocation.report':
                for plan in all_plans:
                    default_wizard_values['analytic_plan_ids'] = [(6, 0, plan.ids)]
                    report_wizard = self.env[report_model].create(default_wizard_values)
                    current_sheet = workbook.add_worksheet('P&L ' + plan.name)
                    report_wizard._inject_report_into_xlsx_sheet(workbook, current_sheet)
            else:
                default_wizard_values['analytic_plan_ids'] = [(6, 0, all_plans.ids)]
                report_wizard = self.env[report_model].create(default_wizard_values)
                current_sheet = workbook.add_worksheet(report_wizard._get_report_name())
                report_wizard._inject_report_into_xlsx_sheet(workbook, current_sheet)

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return {
            'file_name': f'{self._get_report_name()}.xlsx',
            'file_content': generated_file,
            'file_type': 'xlsx',
        }
