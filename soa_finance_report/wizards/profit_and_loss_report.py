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


class PNLAnalyticalReportWizard(models.TransientModel):
    _name = 'soa.profit.and.loss.report'
    _inherit = 'budget.combined.common'
    _description = 'Profit and Loss Report'

    @api.constrains('date_from', 'date_to', 'analytic_plan_ids')
    def check_constrains_fields(self):
        for wizard in self:
            if not wizard.date_from or not wizard.date_to:
                raise UserError(_('Date From and Date to must be required !'))

    def _get_report_name(self):
        return _('Profit and Loss Report')

    def get_analytic_plans(self):
        return f'BU: {", ".join(self._get_analytics_plans().mapped("name"))}'

    def _get_subheader_colums(self, column_keys):
        return []

    def _get_header_colums(self, column_keys):
        columns = []
        mapping_values = {
            'col1': 'Account Description',
            'total': 'TOTAL',
            None: None,
        }
        for key in column_keys:
            if isinstance(key, models.BaseModel):
                name = key.name
            else:
                name = mapping_values.get(key)
            columns.append(name)
        return columns

    def _get_analytics_plans(self):
        if not self.analytic_plan_ids:
            project_plan, _other_plans = self.env['account.analytic.plan']._get_all_plans()
            return (project_plan + _other_plans)
        return self.analytic_plan_ids

    def _column_keys(self):
        """
        columns structure:

        Business Unit 1 |  Business Unit 1  | Business Unit 2 | Business Unit 3 ... | TOTAL
        -----------------------------------------------------------------------------------
        return list of value included in ['clo1', record type, ..., None,
        """
        column_keys = ['col1']
        analytics_plans = self._get_analytics_plans()
        column_keys += [date for date in analytics_plans]
        column_keys += ['total']
        return column_keys

    def get_alloc_rate_in_range_date(self):

        budget_allocation_ids = self.env['account.expense.allocation'].search([
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
            ('budget_id.state', 'in', ('confirm', 'validate', 'done')),
            ('to_analytic_plan_id', '!=', False),
            ('from_analytic_plan_ids', 'not in', [False, []])
        ])
        allocation_grouped = budget_allocation_ids.grouped(lambda a: (a.date_from, a.date_to))
        result = defaultdict(dict)
        for range_date, records in allocation_grouped.items():
            for record in records:
                result[range_date].update({record.to_analytic_plan_id: (record.from_analytic_plan_ids, record.rate)})
        return result

    def get_rate_data(self, month, rate_date_ranges):
        for range_date, result in rate_date_ranges.items():
            date_from, date_to = range_date
            if date_from <= month <= date_to:
                return result
        return {}

    def _get_line_value_by_plan(self, report_line, analytic_plan, first_day_of_months, date_from, date_to):
        """
        return:
            <expression_sum>,
            {
                'plan_id': {
                    (datetime, datetime): <amount>
                }
            }
        """
        struct_report = report_line.report_id
        report_currency = struct_report.financial_report_currency
        currency_table_query = self.env['crossovered.budget.lines']._get_query_currency_table(
            self.env.company.ids, currency_id=report_currency, conversion_date=self.date_to.strftime('%Y-%m-%d'))
        expression_sum = 0.0
        amount_by_date_range_dict = defaultdict(lambda: 0)
        result_groupby_month = defaultdict(lambda: 0.0)
        for expression in report_line.expression_ids.filtered(lambda x: x.engine == 'account_codes'):
            formula = expression.formula.replace(' ', '')
            account_list = ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(formula)
            account_list = [acc.replace('+', '').replace('-', '') for acc in account_list if acc]
            analytic_line_obj = self.env['account.analytic.line']
            analytic_account_ids = self.env['account.analytic.account'].search([
                ('plan_id', "child_of", analytic_plan.id)
            ])
            domain = [
                (f'{analytic_plan._column_name()}', 'in', analytic_account_ids.ids),
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ]
            domain += [('general_account_id.code', 'in', account_list)]
            where_query = analytic_line_obj._where_calc(domain)
            from_clause, where_clause, where_clause_params = where_query.get_sql()
            select = f"""
            SELECT 
                DATE_TRUNC('month', account_analytic_line.date) AS date,
                account_account.code as account_code,
                COALESCE(SUM(account_analytic_line.amount * currency_table.rate), 0.0) AS sum
            FROM {from_clause}
            JOIN {currency_table_query} ON currency_table.company_id = account_analytic_line.company_id
            JOIN account_account ON account_account.id = account_analytic_line.general_account_id
            WHERE {where_clause}
            GROUP BY DATE_TRUNC('month', account_analytic_line.date), 
                    account_account.code
            """

            self.env.cr.execute(select, where_clause_params)
            query_result = self.env.cr.dictfetchall()
            sum_by_account_by_month = defaultdict(lambda: {key: 0.0 for key in account_list})
            for date_val in query_result:
                sum_by_account_by_month[date_val['date'].strftime('%Y-%m-%d')][str(date_val['account_code'])] += date_val['sum']
            # Format of
            # sum_by_account_by_month = {
            #   '2023-12-01': {
            #           '511101': 10.00.
            #       }
            #   }
            for month_str, value_by_account in sum_by_account_by_month.items():
                formula = expression.formula.replace(' ', '')
                for account_code, value in value_by_account.items():
                    formula = re.sub(account_code, f'{value}', formula)
                expression_sum += expr_eval(formula)
                result_groupby_month[month_str] += expr_eval(formula)

        for month in first_day_of_months:
            month_key = month.strftime('%Y-%m-%d')
            amount_by_date_range_dict[month] = round(result_groupby_month[month_key], report_line.report_id.financial_report_currency.decimal_places)
        expression_sum = round(expression_sum, struct_report.financial_report_currency.decimal_places)
        return expression_sum, amount_by_date_range_dict

    def _compute_per_detail_lines(self, report_line):
        single_line_columns = []
        first_day_of_months = self._get_start_days()
        analytics_plans = self._get_analytics_plans()
        date_from = self.date_from
        date_to = self.date_to
        results_2 = {'columns': [], 'result_by_date_range': {}}
        for plan in analytics_plans:
            amount_total, amount_by_date_range_dict = self._get_line_value_by_plan(report_line, plan, first_day_of_months, date_from, date_to)
            single_line_columns.append(amount_total)
            results_2['result_by_date_range'][plan] = amount_by_date_range_dict
        total_of_line = sum(single_line_columns)
        single_line_columns.append(total_of_line)
        results_2['columns'] = single_line_columns
        return results_2

    def _compute_per_total_lines(self, report_line, value_lines, first_day_of_months):
        """"""
        def _check_is_float(to_test):
            try:
                float(to_test)
                return True
            except ValueError:
                return False
        single_line_columns = []
        value_lines_by_code = {line.code or line.id: value for line, value in value_lines.items()}
        column_keys = self._column_keys()[1:]
        term_separator_regex = r'(?<!\de)[+-]|[ ()/*]'
        term_replacement_regex = r"(^|(?<=[ ()+/*-]))%s((?=[ ()+/*-])|$)"
        for col_index in range(len(column_keys)):
            expression_sum = 0.0
            for expression in report_line.expression_ids:
                formula = expression.formula
                terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                 term and not _check_is_float(term) and not keyword.iskeyword(term)]
                for term in terms_to_eval:
                    if not value_lines_by_code.get(term):
                        raise UserError(_('The term of formula in computing total_lines: %s is undefined' % term))
                    term_value = value_lines_by_code[term]['columns'][col_index]
                    formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                try:
                    expression_sum += expr_eval(formula)
                except ZeroDivisionError:
                    expression_sum += 0
                except Exception as e:
                    raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
            single_line_columns.append(
                round(expression_sum, report_line.report_id.financial_report_currency.decimal_places))

        analytics_plans = self._get_analytics_plans()
        result_by_date_range_total_line = defaultdict(lambda: {key: 0.0 for key in first_day_of_months})
        for plan in analytics_plans:
            for month in first_day_of_months:
                range_expression_sum = 0.0
                for expression in report_line.expression_ids:
                    formula = expression.formula
                    terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                     term and not _check_is_float(term) and not keyword.iskeyword(term)]
                    for term in terms_to_eval:
                        if not value_lines_by_code.get(term):
                            raise UserError(_('The term of formula in computing total_lines (result_by_date_range): %s is undefined' % term))
                        term_value = value_lines_by_code[term]['result_by_date_range'][plan][month]
                        formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                    try:
                        range_expression_sum += expr_eval(formula)
                    except ZeroDivisionError:
                        range_expression_sum += 0
                    except Exception as e:
                        raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
                range_expression_sum = round(range_expression_sum, report_line.report_id.financial_report_currency.decimal_places)
                result_by_date_range_total_line[plan][month] = range_expression_sum

        return {'columns': single_line_columns, 'result_by_date_range': result_by_date_range_total_line}

    def _compute_per_allocation_lines(self, report_line, value_lines, first_day_of_months, rate_date_ranges):
        def _check_is_float(to_test):
            try:
                float(to_test)
                return True
            except ValueError:
                return False
        single_line_columns = []
        value_lines_by_code = {line.code or line.id: value for line, value in value_lines.items()}
        term_separator_regex = r'(?<!\de)[+-]|[ ()/*]'
        term_replacement_regex = r"(^|(?<=[ ()+/*-]))%s((?=[ ()+/*-])|$)"

        analytics_plans = self._get_analytics_plans()
        result_by_date_range_total_line = defaultdict(lambda: {key: 0.0 for key in first_day_of_months})
        for plan in analytics_plans:
            plan_expression_sum = 0.0
            for month in first_day_of_months:
                range_expression_sum = 0.0
                for expression in report_line.expression_ids:
                    formula = expression.formula
                    terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                     term and not _check_is_float(term) and not keyword.iskeyword(term)]
                    for term in terms_to_eval:
                        if not value_lines_by_code.get(term):
                            raise UserError(_('The term of formula: in computing allocation_lines %s is undefined' % term))
                        rate_data = self.get_rate_data(month, rate_date_ranges)
                        coeff = rate_data.get(plan, ([], 0.0))[1]
                        from_analytic_plan_ids = rate_data.get(plan, ([], 0.0))[0]
                        source_total_amount = 0.0
                        for src_plan in from_analytic_plan_ids:
                            source_total_amount += value_lines_by_code[term]['result_by_date_range'][src_plan][month]
                        if from_analytic_plan_ids and plan.id not in from_analytic_plan_ids.ids:
                            val = value_lines_by_code[term]['result_by_date_range'][plan].get(month, 0.0)
                            range_expression_sum += val
                        term_value = source_total_amount * coeff / 100
                        if not from_analytic_plan_ids:
                            term_value = -value_lines_by_code[term]['result_by_date_range'][plan][month]
                        formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                    try:
                        range_expression_sum += expr_eval(formula)
                    except ZeroDivisionError:
                        range_expression_sum += 0
                    except Exception as e:
                        raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
                plan_expression_sum += range_expression_sum

                result_by_date_range_total_line[plan][month] = range_expression_sum

            plan_expression_sum = round(
                plan_expression_sum,
                report_line.report_id.financial_report_currency.decimal_places
            )
            single_line_columns.append(plan_expression_sum)

        total_of_line = round(-sum(single_line_columns), report_line.report_id.financial_report_currency.decimal_places)
        single_line_columns.append(total_of_line)

        return {'columns': single_line_columns, 'result_by_date_range': result_by_date_range_total_line}

    def _get_static_line_dict(self, line, value_lines):
        value_dict = {
            'id': line.id,
            'name': line.name,
            'level': 0 if not line.parent_id else 3,
            'code': line.code,
            'has_expression': bool(line.expression_ids),
        }
        if line in value_lines:
            value_dict['columns'] = value_lines[line]['columns']
        return value_dict

    def _get_lines(self):
        structure_report = self.env['account.report'].search([('soa_structure', '=', True)])
        if not structure_report:
            raise UserError(_('Not found SOA structure report!'))

        first_day_of_months = self._get_start_days()
        rate_date_ranges = self.get_alloc_rate_in_range_date()
        before_compute_lines = structure_report.line_ids.filtered(lambda l: not l.compute_after)
        value_lines = {}
        # Detail line by account, report_line has 'expression_ids' and 'parent_id' don't have 'expression_ids'
        detail_line_ids = before_compute_lines.filtered(
            lambda l: l.expression_ids and l.parent_id and not l.parent_id.expression_ids and not l.reallocation_compute)

        for report_line in detail_line_ids:
            line_value = self._compute_per_detail_lines(report_line)
            value_lines[report_line] = line_value

        # Detail line by account groups, report_line has 'expression_ids' and parent_id don't have 'expression_ids'
        total_line_ids = before_compute_lines.filtered(lambda l: l.expression_ids and not l.parent_id and not l.reallocation_compute)
        for report_line in total_line_ids:
            line_value = self._compute_per_total_lines(report_line, value_lines, first_day_of_months)
            value_lines[report_line] = line_value

        reallocation_total_line_ids = before_compute_lines.filtered(lambda l: l.expression_ids and l.reallocation_compute)
        for report_line in reallocation_total_line_ids:
            line_value = self._compute_per_allocation_lines(report_line, value_lines, first_day_of_months, rate_date_ranges)
            value_lines[report_line] = line_value

        after_compute_lines = structure_report.line_ids.filtered(lambda l: l.compute_after)
        for report_line in after_compute_lines:
            line_value = self._compute_per_total_lines(report_line, value_lines, first_day_of_months)
            value_lines[report_line] = line_value

        lines = []
        # Prepare static line
        for line in structure_report.line_ids:
            line_dict = self._get_static_line_dict(line, value_lines)
            lines.append(line_dict)
        column_keys = self._column_keys()
        headers = self._get_header_colums(column_keys)

        return headers, lines

    def _inject_report_into_xlsx_sheet(self, workbook, sheet):
        def write_with_colspan(sheet, x, y, value, colspan, style):
            if colspan == 1:
                sheet.write(y, x, value, style)
            else:
                sheet.merge_range(y, x, y, x + colspan - 1, value, style)

        empty_style = workbook.add_format({'font_name': 'Arial', 'bold': False, 'bottom': 0, 'top': 0})
        title_header_style = workbook.add_format({'align': 'center', 'font_name': 'Arial', 'bold': True, 'bottom': 1, 'top': 1})
        date_default_col1_style = workbook.add_format(
            {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2,
             'num_format': 'yyyy-mm-dd'})
        date_default_style = workbook.add_format(
            {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'num_format': 'yyyy-mm-dd'})
        default_col1_style = workbook.add_format(
            {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True})
        level_0_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666',
             'num_format': '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'})
        level_1_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 1, 'font_color': '#666666'})
        level_2_col1_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_2_col1_total_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_2_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_3_col1_style = workbook.add_format(
            {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        level_3_col1_total_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666',
                                             'num_format': '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'})
        #  Set the first column width to 50
        sheet.set_column(0, 0, 40)

        y_offset = 0
        x_offset = 0
        # Write title and name report first
        period_date_info = self.get_period_info()
        report_name = 'SOA - PROFIT & LOSS ANALYTICAL'

        header_columns, lines = self._get_lines()
        write_with_colspan(sheet, x_offset, y_offset, report_name, 1, title_style)
        y_offset += 1
        write_with_colspan(sheet, x_offset, y_offset, period_date_info, 1, title_style)

        sheet.set_column(1, len(header_columns) - 1, 12)

        x_offset = 0
        y_offset += 1
        # Write header lines
        for header in header_columns:
            write_with_colspan(sheet, x_offset, y_offset, header, 1, title_header_style if header is not None else empty_style)
            x_offset += 1

        y_offset += 1
        for y in range(0, len(lines)):
            level = lines[y].get('level')
            if level == 0:
                style = level_0_style
                col1_style = style
            elif level == 0:
                style = level_0_style
                col1_style = style
            elif level == 1:
                style = level_1_style
                col1_style = style
            elif level == 2:
                style = level_2_style
                col1_style = level_2_col1_style
            elif level == 3:
                style = level_3_style
                col1_style = level_3_col1_style
            else:
                style = default_style
                col1_style = default_col1_style

            x_offset = 0
            sheet.write(y + y_offset, x_offset, lines[y].get('name'), col1_style)
            x_offset += 1

            # Write the remaining columns
            if lines[y].get('columns'):
                for x, column in enumerate(lines[y]['columns'], start=x_offset):
                    _style = style
                    if lines[y]['columns'][x - x_offset] is None:
                        _style = empty_style
                    sheet.write(y + y_offset, x, lines[y]['columns'][x - x_offset], _style)

            if level == 0 and lines[y]['has_expression']:
                y_offset += 1

            # if it's a last line, break down a line
            if y + 1 == len(lines):
                y_offset += y + 1

        y_offset += 1

        x_offset = 0
        period_date_info = self.get_period_info()
        write_with_colspan(sheet, x_offset, y_offset, period_date_info, 1, default_style)

        x_offset = 0
        y_offset += 1
        bu_info = self.get_analytic_plans()
        write_with_colspan(sheet, x_offset, y_offset, bu_info, 1, default_style)

    def action_export_to_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/download/xlsx/%s/%s/%s' % (
                'PNLAnalyticalReport', self._name, self.id)
        }