# -*- coding: utf-8 -*-
import io
import keyword
import re
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import expr_eval
from odoo.addons.soa_finance_report.wizards.budget_report_common import ACCOUNT_CODES_ENGINE_SPLIT_REGEX


class BudgetCombinedReportWizard(models.TransientModel):
    _name = 'budget.combined.report.wizard'
    _inherit = 'budget.combined.common'
    _description = 'Budget Combined Report'

    def _get_report_name(self):
        return _('Budget Combined Report')

    def _get_header_colums(self, first_day_of_months):
        first_column_label = 'Account Description'
        columns = [first_column_label]
        short_months = [month.strftime('%b') for month in first_day_of_months]
        columns += short_months
        columns += ['TOTAL']
        return columns

    def _compute_per_detail_lines(self, report_line, first_day_of_months):
        rates = self._get_currency_rates()
        struct_report = report_line.report_id
        budget_line_model = self.env['crossovered.budget.lines']
        single_line_columns = []
        if report_line.expression_ids:
            for start_day in first_day_of_months:
                budget_line_domain = [
                    # ('currency_id', '=', report_line.report_id.financial_report_currency.id),
                    ('date_from', '=', start_day),
                    ('analytic_plan_id', 'in', self.analytic_plan_ids.ids)
                ]
                expression_sum = 0.0
                for expression in report_line.expression_ids.filtered(lambda x: x.engine == 'account_codes'):
                    formula = expression.formula.replace(' ', '')
                    account_list = ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(formula)
                    account_list = [acc.replace('+', '').replace('-', '') for acc in account_list if acc]
                    value_by_account = {}
                    for account in account_list:
                        domain = budget_line_domain + [('general_budget_id.account_ids.code', '=', account)]
                        budget_lines = budget_line_model.search(domain)
                        if budget_lines:
                            value_by_account[account] = sum([round(
                                line.planned_amount
                                * rates[struct_report.financial_report_currency.id]
                                / rates[line.currency_id.id], struct_report.financial_report_currency.decimal_places)
                                 for line in budget_lines])
                        else:
                            value_by_account[account] = 0.0
                    for account_code, value in value_by_account.items():
                        formula = re.sub(account_code, f'{value}', formula)
                    expression_sum += expr_eval(formula)
                single_line_columns.append(expression_sum)
            total_of_line = sum(single_line_columns)
            single_line_columns.append(total_of_line)
        return single_line_columns

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
        term_separator_regex = r'(?<!\de)[+-]|[ ()/*]'
        term_replacement_regex = r"(^|(?<=[ ()+/*-]))%s((?=[ ()+/*-])|$)"
        for month_indx in range(len(first_day_of_months) + 1):
            expression_sum = 0.0
            for expression in report_line.expression_ids:
                formula = expression.formula
                terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                 term and not _check_is_float(term) and not keyword.iskeyword(term)]
                for term in terms_to_eval:
                    if not value_lines_by_code.get(term):
                        raise UserError(_('The term of formula: %s is undefined', term))
                    term_value = value_lines_by_code[term][month_indx]
                    formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                try:
                    expression_sum += expr_eval(formula)
                except ZeroDivisionError:
                    expression_sum += 0
                except Exception as e:
                    raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))

                single_line_columns.append(round(expression_sum, report_line.report_id.financial_report_currency.decimal_places))
        return single_line_columns

    def _get_static_line_dict(self, line, value_lines):
        value_dict = {
            'id': line.id,
            'name': line.name,
            'level': 0 if not line.parent_id else 3,
            'code': line.code,
            'has_expression': bool(line.expression_ids)
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

        headers = self._get_header_colums(first_day_of_months)

        return headers, lines

    def _inject_report_into_xlsx_sheet(self, workbook, sheet):
        def write_with_colspan(sheet, x, y, value, colspan, style):
            if colspan == 1:
                sheet.write(y, x, value, style)
            else:
                sheet.merge_range(y, x, y, x + colspan - 1, value, style)

        title_header_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'bottom': 1, 'top': 1})
        date_default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2, 'num_format': 'yyyy-mm-dd'})
        date_default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'num_format': 'yyyy-mm-dd'})
        default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True})
        level_0_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666'})
        level_1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 1, 'font_color': '#666666'})
        level_2_col1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_2_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_2_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_3_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        level_3_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})

        #  Set the first column width to 25
        sheet.set_column(0, 0, 25)

        y_offset = 0
        x_offset = 0
        # Write title and name report first
        title_report = 'SOA GROUP'
        report_name = 'BUDGET'
        header_columns, lines = self._get_lines()
        write_with_colspan(sheet, x_offset, y_offset, title_report, 1, title_style)
        y_offset += 1
        write_with_colspan(sheet, x_offset, y_offset, report_name, 1, title_style)
        y_offset += 1

        # Write header lines
        for header in header_columns:
            write_with_colspan(sheet, x_offset, y_offset, header, 1, title_header_style)
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
                    sheet.write(y + y_offset, x, lines[y]['columns'][x-x_offset], style)

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
