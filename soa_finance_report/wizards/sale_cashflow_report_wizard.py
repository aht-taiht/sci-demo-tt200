# -*- coding: utf-8 -*-
import io
import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import expr_eval
from odoo.addons.soa_finance_report.wizards.budget_report_common import ACCOUNT_CODES_ENGINE_SPLIT_REGEX

import logging
_logger = logging.getLogger(__name__)


class SaleCashFlowReportWizard(models.TransientModel):
    _name = 'sale.cashflow.report.wizard'
    _inherit = 'budget.combined.common'
    _description = 'Sale CashFlow Report Wizard'

    company_ids = fields.Many2many('res.company', string='Company')

    @api.model
    def default_get(self, fields_list):
        res = super(SaleCashFlowReportWizard, self).default_get(fields_list)
        res['company_ids'] = [(6, 0, self._context.get('allowed_company_ids', []))]
        return res

    @api.constrains('date_from', 'date_to', 'analytic_plan_ids')
    def check_constrains_fields(self):
        for wizard in self:
            if not wizard.date_from or not wizard.date_to:
                raise UserError(_('Date From and Date to must be required !'))

    def _get_report_name(self):
        return _('CashFlow Report')

    def _get_financial_currency(self):
        currency_id = self.env.ref('base.USD')
        cf_currency = self.env['ir.config_parameter'].sudo().get_param('soa_finance_report.cf_currency_id', False)
        if cf_currency:
            currency_id = self.env['res.currency'].sudo().browse(int(cf_currency))
        return currency_id

    def action_export_to_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/download/xlsx/%s/%s/%s' % (
                'SaleCashFlowReport', self._name, self.id)
        }

    def _get_header_colums(self, column_keys):
        columns = []
        mapping_values = {
            'bu': 'BU',
            'cf': 'CF',
            'total': 'TOTAL',
            None: None,
        }
        year = None
        for key in column_keys:
            if isinstance(key, date):
                name = key.strftime('%b-%y')
                year = key
            else:
                # if key == 'total' and year:
                #     name = "SUM " + year.strftime('%Y')
                if key == 'total':
                    name = "SUM"
                else:
                    name = mapping_values.get(key)
            columns.append(name)
        return columns

    def _column_keys(self):
        column_keys = ['bu', 'cf']
        start_days_of_month = self._get_start_days()
        column_keys += [date for date in start_days_of_month]
        column_keys += ['total', None]
        return column_keys

    def _get_account_bank_cash_initial_balance(self, date):
        financial_currency_id = self.env.ref('base.USD').id
        cf_currency_id = self.env['ir.config_parameter'].sudo().get_param('soa_finance_report.cf_currency_id', False)
        if cf_currency_id:
            financial_currency_id = int(cf_currency_id)

        query = """
            SELECT
                sum(COALESCE(balance * financial_currency_rate / company_currency_rate, 0)) as balance

            FROM (
                SELECT
                    aml.balance as balance,
                    (
                        SELECT
                            COALESCE(
                                (
                                    SELECT r.rate FROM res_currency_rate r
                                    WHERE r.currency_id = c.id AND r.name <= aml.date AND (r.company_id IS NULL OR r.company_id = company.id)
                                    ORDER BY r.company_id, r.name DESC
                                    LIMIT 1
                                ), 1.0) AS rate
                        FROM res_currency c
                        WHERE c.id = financial_currency.id
                    ) as financial_currency_rate,
                    (
                        SELECT
                            COALESCE(
                                (
                                    SELECT r.rate FROM res_currency_rate r
                                    WHERE r.currency_id = c.id AND r.name <= aml.date AND (r.company_id IS NULL OR r.company_id = company.id)
                                    ORDER BY r.company_id, r.name DESC
                                    LIMIT 1
                                ), 1.0) AS rate
                       FROM res_currency c
                       WHERE c.id = company_currency.id
                    ) as company_currency_rate

                FROM account_move_line aml
                JOIN account_account account ON account.id = aml.account_id
                JOIN res_company company ON company.id = aml.company_id
                JOIN res_currency financial_currency ON financial_currency.id = {financial_currency_id}
                JOIN res_currency company_currency ON company_currency.id = aml.company_currency_id
                
                WHERE aml.parent_state = 'posted' AND aml.date < '{date}' 
                    AND account.account_type = 'asset_cash' AND aml.company_id IN {company_ids}
            ) result_table
        """.format(date=date, company_ids=tuple(self.company_ids.ids + [99999]), financial_currency_id=financial_currency_id)

        self._cr.execute(query)
        values = self._cr.fetchall()
        result = 0
        for value in values:
            if value[0]:
                result += value[0]
        return result

    def _get_account_bank_cash_end_balance(self, date):
        financial_currency_id = self.env.ref('base.USD').id
        cf_currency_id = self.env['ir.config_parameter'].sudo().get_param('soa_finance_report.cf_currency_id', False)
        if cf_currency_id:
            financial_currency_id = int(cf_currency_id)

        end_date = date + relativedelta(months=1)
        query = """
            SELECT
                sum(COALESCE(balance *  financial_currency_rate / company_currency_rate, 0)) as balance
            FROM (
                SELECT
                    aml.balance as balance,
                    (
                        SELECT
                            COALESCE(
                                (
                                    SELECT r.rate FROM res_currency_rate r
                                    WHERE r.currency_id = c.id AND r.name <= aml.date AND (r.company_id IS NULL OR r.company_id = company.id)
                                    ORDER BY r.company_id, r.name DESC
                                    LIMIT 1
                                ), 1.0) AS rate
                        FROM res_currency c
                        WHERE c.id = financial_currency.id
                    ) as financial_currency_rate,
                    (
                        SELECT
                            COALESCE(
                                (
                                    SELECT r.rate FROM res_currency_rate r
                                    WHERE r.currency_id = c.id AND r.name <= aml.date AND (r.company_id IS NULL OR r.company_id = company.id)
                                    ORDER BY r.company_id, r.name DESC
                                    LIMIT 1
                                ), 1.0) AS rate
                       FROM res_currency c
                       WHERE c.id = company_currency.id
                    ) as company_currency_rate
                FROM account_move_line aml
                JOIN account_account account ON account.id = aml.account_id
                JOIN res_company company ON company.id = aml.company_id
                JOIN res_currency financial_currency ON financial_currency.id = {financial_currency_id}
                JOIN res_currency company_currency ON company_currency.id = aml.company_currency_id

                WHERE aml.parent_state = 'posted' AND aml.date < '{end_date}' 
                    AND account.account_type = 'asset_cash' AND aml.company_id IN {company_ids}
            ) result_table
        """.format(end_date=end_date, company_ids=tuple(self.company_ids.ids + [99999]), financial_currency_id=financial_currency_id)
        self._cr.execute(query)
        values = self._cr.fetchall()
        result = 0
        for value in values:
            if value[0]:
                result += value[0]
        return result

    def _get_cashflow_lines_bu(self, report_lines, date, analytic_plan_ids=[]):
        reportObj = self.env['account.cashflow.report']
        end_date = date + relativedelta(months=1)
        today = fields.Date.context_today(self)
        this_month = today.month
        this_year = today.year
        actual_in = actual_out = 0
        plan_in = plan_out = 0
        cash_in_bu = cash_out_bu = 0

        def _data_bu_in_month(schedule_date, analytic_plan_id):
            if schedule_date >= date and schedule_date < end_date and \
                    ((analytic_plan_ids and analytic_plan_id in analytic_plan_ids) or not analytic_plan_id):
                return True
            return False

        lines = list(filter(lambda d: _data_bu_in_month(d['schedule_date'], d['analytic_plan_id'][0]), report_lines))

        for line in lines:
            schedule_date_month = line['schedule_date'].month
            schedule_date_year = line['schedule_date'].year

            if (schedule_date_month >= this_month and schedule_date_year == this_year) or (schedule_date_year > this_year):
                # Plan
                if line['amount_financial_currency'] < 0:
                    plan_out += line['amount_financial_currency']
                    cash_out_bu += line['amount_financial_currency']
                else:
                    plan_in += line['amount_financial_currency']
                    cash_in_bu += line['amount_financial_currency']
            else:
                # Actual
                if line['actual_amount_financial_currency'] < 0:
                    actual_out += line['actual_amount_financial_currency']
                    cash_out_bu += line['actual_amount_financial_currency']
                else:
                    actual_in += line['actual_amount_financial_currency']
                    cash_in_bu += line['actual_amount_financial_currency']

        received_margin = actual_in + actual_out
        tobe_margin = plan_in + plan_out
        total_margin = received_margin + tobe_margin
        total_margin_bu = cash_in_bu + cash_out_bu
        result = {
            'actual_in': actual_in, 'actual_out': actual_out, 'received_margin': received_margin,
            'plan_in': plan_in, 'plan_out': plan_out, 'tobe_margin': tobe_margin, 'total_margin': total_margin,
            'cash_in_bu': cash_in_bu, 'cash_out_bu': cash_out_bu, 'total_margin_bu': total_margin_bu
        }
        return result

    def _get_cashflow_lines_project(self, report_lines, date, project_id):
        reportObj = self.env['account.cashflow.report']
        end_date = date + relativedelta(months=1)
        today = fields.Date.context_today(self)
        this_month = today.month
        this_year = today.year

        actual_in = actual_out = 0
        plan_in = plan_out = 0

        def _data_project_in_month(schedule_date, analytic_account_id):
            if schedule_date >= date and schedule_date < end_date and \
                    analytic_account_id == project_id:
                return True
            return False

        lines = list(filter(lambda d: _data_project_in_month(
            d['schedule_date'], d['analytic_account_id'][0]), report_lines))

        for line in lines:
            schedule_date_month = line['schedule_date'].month
            schedule_date_year = line['schedule_date'].year

            if (schedule_date_month >= this_month and schedule_date_year == this_year) or (schedule_date_year > this_year):
                # Plan
                if line['amount_financial_currency'] < 0:
                    plan_out += line['amount_financial_currency']
                else:
                    plan_in += line['amount_financial_currency']
            else:
                # Actual
                if line['actual_amount_financial_currency'] < 0:
                    actual_out += line['actual_amount_financial_currency']
                else:
                    actual_in += line['actual_amount_financial_currency']

        actual_project = actual_in + actual_out
        plan_project = plan_in + plan_out

        result = {
            'actual_in': actual_in, 'actual_out': actual_out, 'actual_project': actual_project,
            'plan_in': plan_in, 'plan_out': plan_out, 'plan_project': plan_project
        }

        return result

    def _get_budget_planned_amount(self, date, analytic_plan_ids=[]):
        BudgetLineObj = self.env['crossovered.budget.lines']
        end_date = date + relativedelta(months=1)

        # domain = [('date_from', '<=', date), ('date_to', '>=', end_date)]
        domain = [('date_from', '=', date), ('company_id', 'in', self.company_ids.ids)]
        if analytic_plan_ids:
            domain += [('analytic_plan_id', 'in', analytic_plan_ids)]

        financial_currency = self._get_financial_currency()
        planned_amount = 0

        budget_lines = BudgetLineObj.search(domain)
        for line in budget_lines:
            planned_amount += line.currency_id._convert(line.planned_amount, financial_currency)
        return planned_amount

    def _get_lines(self):
        column_keys = self._column_keys()
        headers = self._get_header_colums(column_keys)
        reportObj = self.env['account.cashflow.report']
        analyticObj = self.env['account.analytic.account']
        domain = [('schedule_date', '>=', self.date_from), ('schedule_date', '<=',
                   self.date_to), ('company_id', 'in', self.company_ids.ids)]
        if self.analytic_plan_ids:
            domain += [('analytic_plan_id', 'in', self.analytic_plan_ids.ids)]
        else:
            domain += [('analytic_plan_id', '!=', False)]
        report_lines = reportObj.search_read(
            domain=domain, fields=['amount_financial_currency', 'actual_amount_financial_currency', 'schedule_date', 'analytic_plan_id', 'analytic_account_id', 'ref'])
        projects = {}
        projects_name = {}

        for report_line in report_lines:
            analytic_plan_id = report_line['analytic_plan_id'][0]
            analytic_account_id = report_line['analytic_account_id'][0]
            if analytic_plan_id not in projects:
                projects.update({analytic_plan_id: []})
            if analytic_account_id not in projects[report_line['analytic_plan_id'][0]]:
                projects[analytic_plan_id].append(analytic_account_id)
            if analytic_account_id not in projects_name:
                projects_name.update({analytic_account_id: analyticObj.browse(analytic_account_id).name})

        return headers, report_lines, projects, projects_name

    # def _inject_report_into_xlsx_sheet(self, workbook, sheet):
    #     if self.report_type == 'bu':
    #         self._inject_report_into_xlsx_sheet_bu(workbook, sheet)

    def _inject_report_into_xlsx_sheet(self, workbook, sheet):
        def write_with_colspan(sheet, x, y, value, colspan, style):
            if colspan == 1:
                sheet.write(y, x, value, style)
            else:
                sheet.merge_range(y, x, y, x + colspan - 1, value, style)

        def write_with_colspan_y(sheet, x, y, value, colspan, style):
            if colspan == 1:
                sheet.write(y, x, value, style)
            else:
                sheet.merge_range(y, x, y + colspan - 1, x, value, style)

        empty_style = workbook.add_format({'font_name': 'Arial', 'bold': False, 'bottom': 0, 'top': 0})
        header_style_value = {'align': 'center', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        other_header_style = workbook.add_format(header_style_value)

        noborder_header_style_value = {'align': 'center', 'font_name': 'Arial', 'font_size': 11, 'bold': 2}
        noborder_other_header_style = workbook.add_format(noborder_header_style_value)

        bu_header_style_value = {'align': 'left', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        bu_header_style = workbook.add_format(bu_header_style_value)

        month_style_value = {'align': 'center', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        month_style_value.update({'bg_color': '#9dc384', 'font_color': '#45568b'})
        month_header_style = workbook.add_format(month_style_value)

        cf_actual_style_value = {'align': 'left', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        cf_actual_style_value.update({'bg_color': '#dce9d5'})
        cf_actual_style = workbook.add_format(cf_actual_style_value)

        cf_plan_style_value = {'align': 'left', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        cf_plan_style_value.update({'bg_color': '#eecdcd'})
        cf_plan_style = workbook.add_format(cf_plan_style_value)

        cf_project_style_value = {'align': 'center', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        cf_project_style_value.update({'bg_color': '#a7c4e5'})
        cf_project_style = workbook.add_format(cf_project_style_value)

        cf_ref_style_value = {'align': 'right', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        cf_ref_style_value.update({'bg_color': '#ffffff'})
        cf_ref_style = workbook.add_format(cf_ref_style_value)

        cf_margin_style_value = {'align': 'left', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        cf_margin_style_value.update({'bg_color': '#f9da78'})
        cf_margin_style = workbook.add_format(cf_margin_style_value)

        cf_margin_left_style_value = {'align': 'left', 'font_name': 'Arial',
            'font_size': 11, 'bold': 2, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        cf_margin_left_style_value.update({'bg_color': '#f9da78'})
        cf_margin_left_style = workbook.add_format(cf_margin_left_style_value)

        cell_style_value = {'align': 'right', 'font_name': 'Arial', 'font_size': 11,
            'bold': None, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        cell_style_value.update({'bg_color': '#ffffff', 'font_color': '#45568b', 'num_format': '#,##0.00'})
        cell_style = workbook.add_format(cell_style_value)

        noborder_cell_style_value = {'align': 'right', 'font_name': 'Arial', 'font_size': 11, 'bold': None}
        noborder_cell_style_value.update({'font_color': '#45568b', 'num_format': '#,##0.00'})
        noborder_cell_style = workbook.add_format(noborder_cell_style_value)

        cell_gray_style_value = {'align': 'right', 'font_name': 'Arial',
            'font_size': 11, 'bold': None, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        cell_gray_style_value.update({'bg_color': '#b7b7b7', 'font_color': '#45568b', 'num_format': '#,##0.00'})
        cell_gray_style = workbook.add_format(cell_gray_style_value)

        bu_cell_style_value = {'align': 'left', 'valign': 'vcenter', 'font_name': 'Arial',
            'font_size': 11, 'bold': None, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        bu_cell_style = workbook.add_format(bu_cell_style_value)

        bu_operation_style_value = {'align': 'right', 'font_name': 'Arial',
            'font_size': 11, 'bold': 1, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        bu_operation_style_value.update({'bg_color': '#c2d6ec', 'num_format': '#,##0.00'})
        bu_operation_style = workbook.add_format(bu_operation_style_value)

        bu_operation_left_style_value = {'align': 'left', 'font_name': 'Arial',
            'font_size': 11, 'bold': None, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        bu_operation_left_style_value.update({'bg_color': '#c2d6ec', 'text_wrap': True})
        bu_operation_left_style = workbook.add_format(bu_operation_left_style_value)

        total_margin_style_value = {'align': 'right', 'font_name': 'Arial',
            'font_size': 11, 'bold': 0, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        total_margin_style_value.update({'bg_color': '#f9da78', 'num_format': '#,##0.00'})
        total_margin_style = workbook.add_format(total_margin_style_value)

        total_margin_left_style_value = {'align': 'left', 'font_name': 'Arial',
            'font_size': 11, 'bold': 1, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        total_margin_left_style_value.update({'bg_color': '#f9da78'})
        total_margin_left_style = workbook.add_format(total_margin_left_style_value)

        total_budget_style_value = {'align': 'right', 'font_name': 'Arial',
            'font_size': 11, 'bold': 1, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        total_budget_style_value.update({'bg_color': '#f2cda2', 'num_format': '#,##0.00'})
        total_budget_style = workbook.add_format(total_budget_style_value)

        total_budget_left_style_value = {'align': 'left', 'font_name': 'Arial',
            'font_size': 11, 'bold': 1, 'bottom': 1, 'top': 1, 'left': 1, 'right': 1}
        total_budget_left_style_value.update({'bg_color': '#f2cda2'})
        total_budget_left_style = workbook.add_format(total_budget_left_style_value)

        y_offset = 7
        x_offset = 0

        header_columns, report_lines, projects, projects_name = self._get_lines()

        journal_in = {}
        journal_out = {}

        if self.analytic_plan_ids:
            analytic_plan_ids = self.analytic_plan_ids
        else:
            analytic_plan_ids = self.env['account.analytic.plan'].search([])

        for header in header_columns:
            if header == "BU":
                #  Set the column width to 25
                sheet.set_column(x_offset, x_offset, 15)
                write_with_colspan(sheet, x_offset, y_offset, header, 1,
                                   bu_header_style if header is not None else empty_style)
            elif header == 'CF':
                #  Set the column width to 25
                sheet.set_column(x_offset, x_offset, 25)
                write_with_colspan(sheet, x_offset, y_offset, header, 1,
                                   other_header_style if header is not None else empty_style)
            else:
                #  Set the column width to 25
                sheet.set_column(x_offset, x_offset, 20)
                write_with_colspan(sheet, x_offset, y_offset, header, 1,
                                   month_header_style if header is not None else empty_style)
            x_offset += 1

        column_keys = self._column_keys()
        y_offset += 1
        # Lines

        for bu in analytic_plan_ids:
            x_offset = -1
            total_value = {
                'total_actual_in': 0, 'total_actual_out': 0, 'total_actual_project': 0, 'total_received_margin': 0,
                'total_plan_in': 0, 'total_plan_out': 0, 'total_plan_project': 0, 'total_tobe_margin': 0, 'total_total_margin': 0,
            }
            if projects and bu.id in projects:
                total_project_value = {}
                for project in projects[bu.id]:
                    total_project_value.update({project: {
                        'total_actual_project': 0, 'total_actual_in': 0, 'total_actual_out': 0,
                        'total_plan_project': 0, 'total_plan_in': 0, 'total_plan_out': 0
                    }})
                total_project_ref = {'actual_in': {}, 'actual_out': {}, 'plan_in': {}, 'plan_out': {}}

            for key in column_keys:
                if isinstance(key, date):
                    cell_values = self._get_cashflow_lines_bu(report_lines, key, bu.ids)

                    if key not in journal_in:
                        journal_in.update({key: 0})
                    if key not in journal_out:
                        journal_out.update({key: 0})

                    journal_in[key] += cell_values['actual_in']
                    journal_in[key] += cell_values['plan_in']

                    journal_out[key] += cell_values['actual_out']
                    journal_out[key] += cell_values['plan_out']

                    if projects and bu.id in projects:
                        for project in projects[bu.id]:
                            project_value = self._get_cashflow_lines_project(report_lines, key, project)
                            total_project_value[project]['total_actual_in'] += project_value['actual_in']
                            total_project_value[project]['total_actual_out'] += project_value['actual_out']
                            total_project_value[project]['total_actual_project'] += project_value['actual_in']
                            total_project_value[project]['total_actual_project'] += project_value['actual_out']
                            total_project_value[project]['total_plan_in'] += project_value['plan_in']
                            total_project_value[project]['total_plan_out'] += project_value['plan_out']
                            total_project_value[project]['total_plan_project'] += project_value['plan_in']
                            total_project_value[project]['total_plan_project'] += project_value['plan_out']

            y_step = 7
            max_y_offset = y_offset
            for key in column_keys:
                y_offset_tmp = y_offset
                x_offset += 1
                if key == 'bu':
                    # BU
                    # write_with_colspan_y(sheet, x_offset, y_offset, bu.name, y_step, bu_cell_style)
                    pass
                elif key == 'cf':
                    # CF
                    if projects and bu.id in projects:
                        for project in projects[bu.id]:
                            if total_project_value[project]['total_actual_project'] != 0:
                                write_with_colspan(sheet, x_offset, y_offset_tmp,
                                                   projects_name[project], 1, cf_project_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp, "IN", 1, cf_actual_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp, "OUT", 1, cf_actual_style)
                                y_offset_tmp += 1

                    write_with_colspan(sheet, x_offset, y_offset_tmp, "RECEIVED MARGIN", 1, cf_actual_style)
                    y_offset_tmp += 1

                    if projects and bu.id in projects:
                        for project in projects[bu.id]:
                            if total_project_value[project]['total_plan_project'] != 0:
                                write_with_colspan(sheet, x_offset, y_offset_tmp,
                                                   projects_name[project], 1, cf_project_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp, "IN", 1, cf_plan_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp, "OUT", 1, cf_plan_style)
                                y_offset_tmp += 1

                    write_with_colspan(sheet, x_offset, y_offset_tmp, "TO BE MARGIN", 1, cf_plan_style)
                    y_offset_tmp += 1
                    write_with_colspan(sheet, x_offset, y_offset_tmp, "TOTAL MARGIN", 1, cf_margin_style)
                    y_offset_tmp += 1

                elif isinstance(key, date):
                    cell_values = self._get_cashflow_lines_bu(report_lines, key, bu.ids)
                    total_value['total_actual_in'] += cell_values['actual_in']
                    total_value['total_actual_out'] += cell_values['actual_out']
                    total_value['total_actual_project'] += cell_values['actual_in']
                    total_value['total_actual_project'] += cell_values['actual_out']
                    total_value['total_received_margin'] += cell_values['received_margin']
                    total_value['total_plan_in'] += cell_values['plan_in']
                    total_value['total_plan_out'] += cell_values['plan_out']
                    total_value['total_plan_project'] += cell_values['plan_in']
                    total_value['total_plan_project'] += cell_values['plan_out']
                    total_value['total_tobe_margin'] += cell_values['tobe_margin']
                    total_value['total_total_margin'] += cell_values['total_margin']

                    if projects and bu.id in projects:
                        for project in projects[bu.id]:
                            project_value = self._get_cashflow_lines_project(report_lines, key, project)
                            if total_project_value[project]['total_actual_project'] != 0:
                                write_with_colspan(sheet, x_offset, y_offset_tmp, project_value['actual_project']
                                                   if project_value['actual_project'] != 0 else '-', 1, cell_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp,
                                           project_value['actual_in'] if project_value['actual_in'] != 0 else '-', 1, cell_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp,
                                           project_value['actual_out'] if project_value['actual_out'] != 0 else '-', 1, cell_style)
                                y_offset_tmp += 1

                    write_with_colspan(sheet, x_offset, y_offset_tmp, cell_values['received_margin']
                                       if cell_values['received_margin'] != 0 else '-', 1, cell_gray_style)
                    y_offset_tmp += 1

                    if projects and bu.id in projects:
                        for project in projects[bu.id]:
                            project_value = self._get_cashflow_lines_project(report_lines, key, project)
                            if total_project_value[project]['total_plan_project'] != 0:
                                write_with_colspan(sheet, x_offset, y_offset_tmp, project_value['plan_project']
                                                   if project_value['plan_project'] != 0 else '-', 1, cell_gray_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp,
                                           project_value['plan_in'] if project_value['plan_in'] != 0 else '-', 1, cell_gray_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp,
                                                   project_value['plan_out'] if project_value['plan_out'] != 0 else '-', 1, cell_gray_style)
                                y_offset_tmp += 1

                    write_with_colspan(sheet, x_offset, y_offset_tmp, cell_values['tobe_margin']
                                       if cell_values['tobe_margin'] != 0 else '-', 1, cell_gray_style)
                    y_offset_tmp += 1
                    write_with_colspan(sheet, x_offset, y_offset_tmp, cell_values['total_margin']
                                       if cell_values['total_margin'] != 0 else '-', 1, cell_gray_style)
                    y_offset_tmp += 1

                elif key == 'total':

                    if projects and bu.id in projects:
                        for project in projects[bu.id]:
                            if total_project_value[project]['total_actual_project'] != 0:
                                write_with_colspan(sheet, x_offset, y_offset_tmp, total_project_value[project]['total_actual_project']
                                                   if total_project_value[project]['total_actual_project'] != 0 else '-', 1, cell_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp, total_project_value[project]['total_actual_in']
                                           if total_project_value[project]['total_actual_in'] != 0 else '-', 1, cell_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp, total_project_value[project]['total_actual_out']
                                                   if total_project_value[project]['total_actual_out'] != 0 else '-', 1, cell_style)
                                y_offset_tmp += 1

                    write_with_colspan(sheet, x_offset, y_offset_tmp, total_value['total_received_margin']
                                       if total_value['total_received_margin'] != 0 else '-', 1, cell_gray_style)
                    y_offset_tmp += 1

                    if projects and bu.id in projects:
                        for project in projects[bu.id]:
                            if total_project_value[project]['total_plan_project'] != 0:
                                write_with_colspan(sheet, x_offset, y_offset_tmp, total_project_value[project]['total_plan_project']
                                                   if total_project_value[project]['total_plan_project'] != 0 else '-', 1, cell_gray_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp, total_project_value[project]['total_plan_in']
                                           if total_project_value[project]['total_plan_in'] != 0 else '-', 1, cell_gray_style)
                                y_offset_tmp += 1
                                write_with_colspan(sheet, x_offset, y_offset_tmp, total_project_value[project]['total_plan_out']
                                                   if total_project_value[project]['total_plan_out'] != 0 else '-', 1, cell_gray_style)
                                y_offset_tmp += 1

                    write_with_colspan(sheet, x_offset, y_offset_tmp, total_value['total_tobe_margin']
                                       if total_value['total_tobe_margin'] != 0 else '-', 1, cell_gray_style)
                    y_offset_tmp += 1
                    write_with_colspan(sheet, x_offset, y_offset_tmp, total_value['total_total_margin']
                                       if total_value['total_total_margin'] != 0 else '-', 1, cell_gray_style)
                    y_offset_tmp += 1

                if y_offset_tmp > max_y_offset:
                    max_y_offset = y_offset_tmp

            write_with_colspan_y(sheet, 0, y_offset, bu.name, max_y_offset - y_offset, bu_cell_style)
            y_offset = max_y_offset

        total_value = {'total_cash_in_bu': 0, 'total_cash_out_bu': 0, 'total_total_margin_bu': 0}
        # CASH-IN BU OPERATION
        x_offset = -1
        for key in column_keys:
            y_offset_tmp = y_offset
            x_offset += 1
            if key == 'bu':
                # BU
                cash_in = """CASH-IN BU OPERATION"""
                write_with_colspan_y(sheet, x_offset, y_offset, cash_in, 1, bu_operation_left_style)
            elif key == 'cf':
                # CF
                write_with_colspan(sheet, x_offset, y_offset_tmp, "", 1, bu_operation_style)
                y_offset_tmp += 1
            elif isinstance(key, date):
                cell_values = self._get_cashflow_lines_bu(report_lines, key, analytic_plan_ids.ids)
                total_value['total_cash_in_bu'] += cell_values['cash_in_bu']
                write_with_colspan(sheet, x_offset, y_offset_tmp,
                                   cell_values['cash_in_bu'] if cell_values['cash_in_bu'] != 0 else '-', 1, bu_operation_style)
                y_offset_tmp += 1
            elif key == 'total':
                write_with_colspan(sheet, x_offset, y_offset_tmp, total_value['total_cash_in_bu']
                                   if total_value['total_cash_in_bu'] != 0 else '-', 1, bu_operation_style)
                sheet.set_column(x_offset, x_offset, 20)
                y_offset_tmp += 1
        y_offset += 1

        # CASH-OUT BU OPERATION
        x_offset = -1
        for key in column_keys:
            y_offset_tmp = y_offset
            x_offset += 1
            if key == 'bu':
                # BU
                cash_out = """CASH-OUT BU OPERATION"""
                write_with_colspan_y(sheet, x_offset, y_offset, cash_out, 1, bu_operation_left_style)
            elif key == 'cf':
                # CF
                write_with_colspan(sheet, x_offset, y_offset_tmp, "", 1, bu_operation_style)
                y_offset_tmp += 1
            elif isinstance(key, date):
                cell_values = self._get_cashflow_lines_bu(report_lines, key, analytic_plan_ids.ids)
                total_value['total_cash_out_bu'] += cell_values['cash_out_bu']
                write_with_colspan(sheet, x_offset, y_offset_tmp,
                                   cell_values['cash_out_bu'] if cell_values['cash_out_bu'] != 0 else '-', 1, bu_operation_style)
                y_offset_tmp += 1
            elif key == 'total':
                write_with_colspan(sheet, x_offset, y_offset_tmp, total_value['total_cash_out_bu']
                                   if total_value['total_cash_out_bu'] != 0 else '-', 1, bu_operation_style)
                sheet.set_column(x_offset, x_offset, 20)
                y_offset_tmp += 1
        y_offset += 1

        # TOTAL MARGIN
        x_offset = 0
        write_with_colspan(sheet, x_offset, y_offset, "TOTAL MARGIN", 1, total_margin_left_style)
        x_offset = 1
        write_with_colspan(sheet, x_offset, y_offset, "", 1, total_margin_style)
        for key in column_keys:
            if isinstance(key, date):
                x_offset += 1
                cell_values = self._get_cashflow_lines_bu(report_lines, key, analytic_plan_ids.ids)
                total_value['total_total_margin_bu'] += cell_values['total_margin_bu']
                write_with_colspan(sheet, x_offset, y_offset, cell_values['total_margin_bu']
                                   if cell_values['total_margin_bu'] != 0 else '-', 1, total_margin_style)
            elif key == 'total':
                x_offset += 1
                write_with_colspan(sheet, x_offset, y_offset, total_value['total_total_margin_bu']
                                   if total_value['total_total_margin_bu'] != 0 else '-', 1, total_margin_style)
                sheet.set_column(x_offset, x_offset, 20)
        y_offset += 1

        # Budget by BU
        for bu in analytic_plan_ids:
            total_budget_bu = 0
            x_offset = 0
            write_with_colspan(sheet, x_offset, y_offset, bu.name, 1, bu_cell_style)
            x_offset = 1
            write_with_colspan(sheet, x_offset, y_offset, "", 1, cell_style)
            for key in column_keys:
                if isinstance(key, date):
                    x_offset += 1
                    budget_bu = self._get_budget_planned_amount(key, bu.ids)
                    total_budget_bu += budget_bu
                    write_with_colspan(sheet, x_offset, y_offset, budget_bu if budget_bu != 0 else '-', 1, cell_style)
                elif key == 'total':
                    x_offset += 1
                    write_with_colspan(sheet, x_offset, y_offset,
                                       total_budget_bu if total_budget_bu != 0 else '-', 1, cell_style)
                    sheet.set_column(x_offset, x_offset, 20)
            y_offset += 1

        # TOTAL BUDGET
        x_offset = 0
        write_with_colspan(sheet, x_offset, y_offset, "TOTAL BUDGET", 1, total_budget_left_style)
        x_offset = 1
        write_with_colspan(sheet, x_offset, y_offset, "", 1, total_budget_style)
        total_total_budget = 0
        for key in column_keys:
            if isinstance(key, date):
                x_offset += 1
                total_budget = self._get_budget_planned_amount(key, analytic_plan_ids.ids)
                total_total_budget += total_budget
                write_with_colspan(sheet, x_offset, y_offset, total_budget if total_budget !=
                                   0 else '-', 1, total_budget_style)
            elif key == 'total':
                x_offset += 1
                write_with_colspan(sheet, x_offset, y_offset,
                                   total_total_budget if total_total_budget != 0 else '-', 1, total_budget_style)
                sheet.set_column(x_offset, x_offset, 20)
        y_offset += 1
        # # CUMUL FORECAST
        # x_offset = 0
        # write_with_colspan(sheet, x_offset, y_offset, "CUMUL FORECAST", 1, bu_cell_style)
        # x_offset = 1
        # write_with_colspan(sheet, x_offset, y_offset, "", 1, cell_style)
        # for key in column_keys:
        #     if isinstance(key, date):
        #         x_offset += 1
        #         write_with_colspan(sheet, x_offset, y_offset, '-', 1, cell_style)
        #     elif key == 'total':
        #         x_offset += 1
        #         write_with_colspan(sheet, x_offset, y_offset, '-', 1, cell_style)
        #         sheet.set_column(x_offset, x_offset, 20)
        # y_offset += 1
        # # PROJECTION WITH FORCAST
        # x_offset = 0
        # write_with_colspan(sheet, x_offset, y_offset, "TOTAL BUDGET", 1, bu_cell_style)
        # x_offset = 1
        # write_with_colspan(sheet, x_offset, y_offset, "", 1, cell_style)
        # for key in column_keys:
        #     if isinstance(key, date):
        #         x_offset += 1
        #         write_with_colspan(sheet, x_offset, y_offset, '-', 1, cell_style)
        #     elif key == 'total':
        #         x_offset += 1
        #         write_with_colspan(sheet, x_offset, y_offset, '-', 1, cell_style)
        #         sheet.set_column(x_offset, x_offset, 20)
        # y_offset += 1

        journal_init = {}
        # BB
        y_offset = 1
        x_offset = -1
        for key in column_keys:
            y_offset_tmp = y_offset
            x_offset += 1
            if key == 'bu':
                # BU
                write_with_colspan_y(sheet, x_offset, y_offset, "", 1, empty_style)
            elif key == 'cf':
                # CF
                write_with_colspan(sheet, x_offset, y_offset_tmp, "BB", 1, noborder_other_header_style)
            elif isinstance(key, date):
                if key not in journal_init:
                    journal_init.update({key: 0})
                # init_balance = self._get_journal_initial_balance(key)
                init_balance = self._get_account_bank_cash_initial_balance(key)
                journal_init[key] += init_balance
                write_with_colspan(sheet, x_offset, y_offset_tmp, init_balance if init_balance !=
                                   0 else '-', 1, noborder_cell_style)
        y_offset += 1

        # IN
        x_offset = -1
        for key in column_keys:
            y_offset_tmp = y_offset
            x_offset += 1
            if key == 'bu':
                # BU
                write_with_colspan_y(sheet, x_offset, y_offset, "", 1, empty_style)
            elif key == 'cf':
                # CF
                write_with_colspan(sheet, x_offset, y_offset_tmp, "IN", 1, noborder_other_header_style)
            elif isinstance(key, date):
                init_balance = journal_in[key]
                write_with_colspan(sheet, x_offset, y_offset_tmp, init_balance if init_balance !=
                                   0 else '-', 1, noborder_cell_style)
        y_offset += 1
        y_offset += 1

        # OUT
        x_offset = -1
        for key in column_keys:
            y_offset_tmp = y_offset
            x_offset += 1
            if key == 'bu':
                # BU
                write_with_colspan_y(sheet, x_offset, y_offset, "", 1, empty_style)
            elif key == 'cf':
                # CF
                write_with_colspan(sheet, x_offset, y_offset_tmp, "OUT", 1, noborder_other_header_style)
            elif isinstance(key, date):
                init_balance = journal_out[key]
                write_with_colspan(sheet, x_offset, y_offset_tmp, init_balance if init_balance !=
                                   0 else '-', 1, noborder_cell_style)
        y_offset += 1

        # EB
        x_offset = -1
        for key in column_keys:
            y_offset_tmp = y_offset
            x_offset += 1
            if key == 'bu':
                # BU
                write_with_colspan_y(sheet, x_offset, y_offset, "", 1, empty_style)
            elif key == 'cf':
                # CF
                write_with_colspan(sheet, x_offset, y_offset_tmp, "EB", 1, noborder_other_header_style)
            elif isinstance(key, date):
                init_balance = journal_init[key] + journal_in[key] + journal_out[key]
                write_with_colspan(sheet, x_offset, y_offset_tmp, init_balance if init_balance !=
                                   0 else '-', 1, noborder_cell_style)
        y_offset += 1

        # EB from bank/cash journal
        x_offset = -1
        for key in column_keys:
            y_offset_tmp = y_offset
            x_offset += 1
            if key == 'bu':
                # BU
                write_with_colspan_y(sheet, x_offset, y_offset, "", 1, empty_style)
            elif key == 'cf':
                # CF
                write_with_colspan(sheet, x_offset, y_offset_tmp, "EB from bank/cash journal",
                                   1, noborder_other_header_style)
            elif isinstance(key, date):
                today = fields.Date.context_today(self)
                this_month = today.month
                this_year = today.year

                key_month = key.month
                key_year = key.year

                if (key_month >= this_month and key_year == this_year) or (key_year > this_year):
                    end_balance = 0
                else:
                    # end_balance = self._get_journal_end_balance(key)
                    end_balance = self._get_account_bank_cash_end_balance(key)
                write_with_colspan(sheet, x_offset, y_offset_tmp, end_balance if end_balance !=
                                   0 else '-', 1, noborder_cell_style)
        y_offset += 1
