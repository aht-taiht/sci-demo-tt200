# -*- coding: utf-8 -*-
import io
import keyword
import re
from datetime import datetime, date

import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import expr_eval

from odoo.addons.soa_finance_report.wizards.budget_report_common import ACCOUNT_CODES_ENGINE_SPLIT_REGEX


class BudgetReforecastReportWizard(models.TransientModel):
    _name = 'budget.reforecast.combined.report'
    _inherit = 'budget.combined.common'
    _description = 'Budget Combined Report'

    def _get_report_name(self):
        return _('Budget Reforecast Report')

    def _get_subheader_colums(self, column_keys):
        # Not include col 1
        subheaders = []
        column_keys = column_keys[1:]
        date_list = filter(lambda x: isinstance(x, date), column_keys)
        for col_key in date_list:
            if col_key.month < fields.date.today().month:
                value = {
                    'name': _('Actual'),
                    'colspan': 1
                }
            else:
                value = {
                    'name': _('Forecast'),
                    'colspan': 1
                }
            subheaders.append(value)
        none_val = {'name': None, 'colspan': 1}
        current_group_header_val = {'name': 'Reforecast vs Budget', 'colspan': 4}
        compare_group_header_val = {'name': 'Reforecast vs Last year', 'colspan': 4}
        subheaders += [none_val, none_val, current_group_header_val, none_val, compare_group_header_val]
        return subheaders

    def _get_header_colums(self, column_keys):
        columns = []
        mapping_values = {
            'col1': 'Account Description',
            'total': 'TOTAL',
            'reforecast': 'Reforecast',
            'budget': 'Budget',
            'variant': 'Variant',
            'variant_%': 'Variant %',
            'last_y_budget': 'Last Y',
            'variant_2': 'Variant',
            'variant_2_%': 'Variant %',
            None: None,
        }
        for key in column_keys:
            if isinstance(key, date):
                name = key.strftime('%b')
            else:
                name = mapping_values.get(key)
            columns.append(name)
        return columns

    def _column_keys(self):
        """
columns structure:

actual  | forecast | ...note current time |       |------------ Reforecast vs Budget --------------------|              |-------Reforecast vs Last year----------|
-----------------------------------------------------------------------------------------------------------------------------------------------------------------
Month_1 | Month_2 | ...month_in_range... | TOTAL | [_empty_] | Reforecase | Budget | Variant | Variant % | [__empty__] | Reforecase | Budget | Variant | Variant %
return list of value included in ['clo1', datetime type, ..., None,
"""
        column_keys = ['col1']
        start_days_of_month = self._get_start_days()
        column_keys += [date for date in start_days_of_month]
        column_keys += ['total', None]
        column_keys += ['reforecast', 'budget', 'variant', 'variant_%', None, 'reforecast', 'last_y_budget', 'variant_2', 'variant_2_%']
        return column_keys

    def _get_budget_line_by_domain(self, account_code, start_day):
        budget_line_model = self.env['crossovered.budget.lines']
        budget_line_domain = [
            ('date_from', '=', start_day),
            ('analytic_plan_id', 'in', self.analytic_plan_ids.ids),
            ('crossovered_budget_id.state', 'not in', ('draft', 'cancel'))
        ]
        domain = budget_line_domain + [('general_budget_id.account_ids.code', '=', account_code)]
        return budget_line_model.search(domain)

    def _get_line_value_by_start_day(self, report_line, start_day, is_last_year=False):
        struct_report = report_line.report_id
        rates = self._get_currency_rates()

        planned_expression_sum = 0.0
        practical_expression_sum = 0.0  # if the date is the current or future date, get the reforecast_amount
        is_past_month = start_day.month < fields.date.today().month
        for expression in report_line.expression_ids.filtered(lambda x: x.engine == 'account_codes'):
            formula = practical_formula = planned_formula = expression.formula.replace(' ', '')
            account_list = ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(formula)
            account_list = [acc.replace('+', '').replace('-', '') for acc in account_list if acc]
            practical_value_by_account = {}
            planned_value_by_account = {}
            for account in account_list:
                budget_lines = self._get_budget_line_by_domain(account, start_day)
                if budget_lines:
                    practical_value_by_account[account] = sum([round(
                        (line.practical_amount if is_past_month else line.reforecast_amount)
                        * rates[struct_report.financial_report_currency.id]
                        / rates[line.currency_id.id],
                        struct_report.financial_report_currency.decimal_places)
                        for line in budget_lines])
                    planned_value_by_account[account] = sum([round(
                        is_last_year and line.reforecast_amount or line.planned_amount
                        * rates[struct_report.financial_report_currency.id]
                        / rates[line.currency_id.id],
                        struct_report.financial_report_currency.decimal_places)
                        for line in budget_lines])
                else:
                    practical_value_by_account[account] = 0.0
                    planned_value_by_account[account] = 0.0
            for account_code, value in practical_value_by_account.items():
                practical_formula = re.sub(account_code, f'{value}', practical_formula)
            for account_code, value in planned_value_by_account.items():
                planned_formula = re.sub(account_code, f'{value}', planned_formula)
            planned_expression_sum += expr_eval(planned_formula)
            practical_expression_sum += expr_eval(practical_formula)

        return planned_expression_sum, practical_expression_sum

    def _compute_per_detail_lines(self, report_line, first_day_of_months):
        # rates = self._get_currency_rates()
        practical_single_line_columns = []
        planned_single_line_columns = []

        for start_day in first_day_of_months:
            planned_expression_sum = 0.0
            practical_expression_sum = 0.0  # if the date is the current or future date, get the reforecast_amount
            planned_expression_sum, practical_expression_sum = self._get_line_value_by_start_day(report_line, start_day)
            practical_single_line_columns.append(practical_expression_sum)
            planned_single_line_columns.append(planned_expression_sum)

        # Practical Budget Total in the current year
        # Compute Column N (Total) = Column P (Reforecast) = Column U (Reforecast) = Budget Total
        practical_total_of_line = sum(practical_single_line_columns)
        # Add Practical Budget Total Column
        practical_single_line_columns.append(practical_total_of_line)

        # Compute Planned Budget Total in the current year : Column Q
        planned_total_of_line = sum(planned_single_line_columns)
        # Variant in the current year: Column R = Column P - Column Q
        current_variant_amount = practical_total_of_line - planned_total_of_line
        # Variance % in the current: Column S =  Column R / Column Q
        current_variant_percent = round(current_variant_amount / planned_total_of_line * 100 if planned_total_of_line else 0.0)

        # Compute Last year Planned Budget : Column U
        last_year_planned_single_line_columns = []
        for start_day in first_day_of_months:
            start_day = start_day - relativedelta(years=1)
            last_y_planned_expression_sum, last_y_practical_expression_sum = self._get_line_value_by_start_day(report_line, start_day, is_last_year=True)
            last_year_planned_single_line_columns.append(last_y_planned_expression_sum)
        last_year_planned_total_of_line = sum(last_year_planned_single_line_columns)
        # Variant in the last year: Column W = Column U - Column V
        last_y_variant_amount = practical_total_of_line - last_year_planned_total_of_line
        # Variance % in the last year: Column X = Column W / V
        last_y_variant_percent = round(last_y_variant_amount / last_year_planned_total_of_line * 100 if last_year_planned_total_of_line else 0.0)

        results = [
            *practical_single_line_columns,
            None,  # Column O
            practical_total_of_line,  # Column P
            planned_total_of_line,  # Column Q
            current_variant_amount,  # Column R
            current_variant_percent,  # Column S
            None,  # Column T
            practical_total_of_line,  # Column U
            last_year_planned_total_of_line,  # Column V
            last_y_variant_amount,  # Column W
            last_y_variant_percent,  # Column X
        ]
        return results

    def _compute_per_total_lines(self, report_line, first_day_of_months, value_lines):
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
            column_key = column_keys[col_index]
            if isinstance(column_key, date) or column_key in ['total', 'reforecast', 'variant', 'variant_2', 'budget', 'last_y_budget']:
                expression_sum = 0.0
                for expression in report_line.expression_ids:
                    formula = expression.formula
                    terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                     term and not _check_is_float(term) and not keyword.iskeyword(term)]
                    for term in terms_to_eval:
                        if not value_lines_by_code.get(term):
                            raise UserError(_('The term of formula: %s is undefined' % term))
                        term_value = value_lines_by_code[term][col_index]
                        formula = re.sub(term, f'{term_value}', formula)
                    try:
                        expression_sum += expr_eval(formula)
                    except ZeroDivisionError:
                        expression_sum += 0
                    except Exception as e:
                        raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))

                single_line_columns.append(
                    round(expression_sum, report_line.report_id.financial_report_currency.decimal_places))
            elif column_key in ['variant_%', 'variant_2_%']:
                single_line_columns.append(None if not report_line.expression_ids else '%%%')
            else:
                single_line_columns.append(None)

        COLUMN_STEP = 0
        if report_line.expression_ids:
            number_of_months = len(list(filter(lambda x: isinstance(x, date), column_keys)))
            variant = single_line_columns[number_of_months + 4]
            budget = single_line_columns[number_of_months + 3]
            variant_percent = round(variant / budget * 100 if budget else 0)

            COLUMN_STEP += 5
            variant_2 = single_line_columns[number_of_months + 4 + COLUMN_STEP]
            budget_2 = single_line_columns[number_of_months + 3 + COLUMN_STEP]
            variant_percent_2 = round(variant_2 / budget_2 * 100 if budget_2 else 0)

            single_line_columns[number_of_months + 5] = variant_percent
            single_line_columns[number_of_months + 5 + COLUMN_STEP * 1] = variant_percent_2

        return single_line_columns

    def _get_static_line_dict(self, line, value_lines):
        value_dict = {
            'id': line.id,
            'name': line.name,
            'level': 0 if not line.parent_id else 3,
            'code': line.code,
            'has_expression': bool(line.expression_ids),
        }
        if line in value_lines:
            value_dict['columns'] = value_lines[line]
        return value_dict

    def _get_lines(self):
        structure_report = self.env['account.report'].search([('soa_structure', '=', True)])
        if not structure_report:
            raise UserError(_('Not found SOA structure report!'))

        first_day_of_months = self._get_start_days()
        value_lines = {}
        # Detail line by account, report_line has 'expression_ids' and 'parent_id' don't have 'expression_ids'
        detail_line_ids = structure_report.line_ids.filtered(
            lambda l: l.expression_ids and l.parent_id and not l.parent_id.expression_ids)
        for report_line in detail_line_ids:
            line_value = self._compute_per_detail_lines(report_line, first_day_of_months)
            value_lines[report_line] = line_value

        # Detail line by account groups, report_line has 'expression_ids' and parent_id don't have 'expression_ids'
        total_line_ids = structure_report.line_ids.filtered(lambda l: l.expression_ids and not l.parent_id)
        for report_line in total_line_ids:
            line_value = self._compute_per_total_lines(report_line, first_day_of_months, value_lines)
            value_lines[report_line] = line_value

        lines = []
        # Prepare static line
        for line in structure_report.line_ids.filtered(lambda li: '%' not in li.name):
            line_dict = self._get_static_line_dict(line, value_lines)
            lines.append(line_dict)

        column_keys = self._column_keys()
        headers = self._get_header_colums(column_keys)
        sub_headers = self._get_subheader_colums(column_keys)

        return sub_headers, headers, lines

    def _inject_report_into_xlsx_sheet(self, workbook, sheet):
        def write_with_colspan(sheet, x, y, value, colspan, style):
            if colspan == 1:
                sheet.write(y, x, value, style)
            else:
                sheet.merge_range(y, x, y, x + colspan - 1, value, style)

        empty_style = workbook.add_format({'font_name': 'Arial', 'bold': False, 'bottom': 0, 'top': 0})
        title_header_style = workbook.add_format({'align': 'center', 'font_name': 'Arial', 'bold': True, 'bottom': 1, 'top': 1})
        actual_sub_header_style = workbook.add_format({'align': 'center', 'font_name': 'Arial', 'font_color': '#ff0000', 'bold': False, 'bottom': 0, 'top': 0})
        reforecast_sub_header_style = workbook.add_format({'align': 'center', 'font_name': 'Arial', 'font_color': '#6aa84f', 'bold': False, 'bottom': 0, 'top': 0})
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
            {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666'})
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
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})

        #  Set the first column width to 25
        sheet.set_column(0, 0, 25)

        y_offset = 0
        x_offset = 0
        # Write title and name report first
        title_report = 'SOA GROUP'
        report_name = 'BUDGET'
        subheaders, header_columns, lines = self._get_lines()
        write_with_colspan(sheet, x_offset, y_offset, title_report, 1, title_style)
        y_offset += 1
        write_with_colspan(sheet, x_offset, y_offset, report_name, 1, title_style)

        # Write subheaders
        for col_indx in range(0, len(subheaders)):
            col_val = subheaders[col_indx]
            colspan = col_val.get('colspan')
            if col_val.get('name') == _('Actual'):
                write_with_colspan(sheet, x_offset + col_indx + 1, y_offset, col_val.get('name'), 1, actual_sub_header_style)
            elif col_val.get('name') == _('Forecast'):
                write_with_colspan(sheet, x_offset + col_indx + 1, y_offset, col_val.get('name'), 1, reforecast_sub_header_style)
            elif col_val.get('name'):
                write_with_colspan(sheet, x_offset + col_indx + 1, y_offset, col_val.get('name'), colspan, title_header_style)
                x_offset += colspan - 1
            else:
                write_with_colspan(sheet, x_offset + col_indx + 1, y_offset, '', 1, empty_style)

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

        x_offset = 0
        period_date_info = self.get_period_info()
        write_with_colspan(sheet, x_offset, y_offset, period_date_info, 1, default_style)

        y_offset += 1
        bu_info = self.get_analytic_plans()
        write_with_colspan(sheet, x_offset, y_offset, bu_info, 1, default_style)

    def action_export_to_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/download/xlsx/%s/%s/%s' % (
                'BudgetReforecastReport', self._name, self.id)
        }
