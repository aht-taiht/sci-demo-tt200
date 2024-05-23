# -*- coding: utf-8 -*-
import calendar
import io
import re
from collections import defaultdict
from datetime import datetime, date
import keyword

import xlsxwriter
from dateutil.relativedelta import relativedelta
from odoo import osv
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import expr_eval

from odoo.addons.soa_finance_report.wizards.budget_report_common import ACCOUNT_CODES_ENGINE_SPLIT_REGEX


class PnLAllocationBUReportWizard(models.TransientModel):
    _name = 'profit.and.loss.bu.allocation.report'
    _inherit = 'budget.combined.common'
    _description = 'Profit and Loss BU Allocation Report'

    def _get_report_name(self):
        return _('Profit and Loss BU Allocation Report')

    def get_analytic_plans(self):
        return f'BU: {", ".join(self._get_analytics_plans().mapped("name"))}'

    def _get_subheader_colums(self, column_keys):
        # Not include col 1
        subheaders = []
        column_keys = column_keys[1:]
        date_list = filter(lambda x: isinstance(x, date), column_keys)
        none_val = {'name': None, 'colspan': 1}

        for col_key in date_list:
            subheaders.append(none_val)
        today = fields.Date.today()
        month_current = self.date_to if self.date_to < today else today
        year_current = self.date_to.year
        subheader_1_val = {'name': '%s MTD' % month_current.strftime('%b-%y'), 'colspan': 4}
        subheader_2_val = {'name': '%s YTD' % month_current.strftime('%b-%y'), 'colspan': 4}
        subheader_3_val = {'name': '%s vs %s YTD' % (year_current, year_current-1), 'colspan': 4}
        subheader_4_val = {'name': '%s vs %s MTD' % (year_current, year_current-1), 'colspan': 4}
        subheaders += [
            none_val, none_val,
            subheader_1_val, none_val,
            subheader_2_val, none_val,
            subheader_3_val, none_val,
            subheader_4_val]
        return subheaders

    def _get_header_colums(self, column_keys):
        columns = []
        try:
            mtd_pre_year = self.date_to.replace(year=self.date_to.year - 1).strftime('%Y')
        except ValueError:
            mtd_pre_year = self.date_to.replace(year=self.date_to.year - 1, day=self.date_to.day-1).strftime('%Y')
        try:
            ytd_pre_year = self.date_to.replace(year=self.date_to.year - 1).strftime('%Y')
        except ValueError:
            ytd_pre_year = self.date_to.replace(year=self.date_to.year - 1, day=self.date_to.day-1).strftime('%Y')
        mapping_values = {
            'col1': 'Account Description',
            'total': 'TOTAL',
            'actual': 'Actual',
            'budget': 'Budget',
            'variant': 'Variant',
            'variant_percent': 'Variant %',
            'mtd_current_year': 'MTD' + ' ' + self.date_to.strftime('%Y'),
            'mtd_pre_year': 'MTD' + ' ' + mtd_pre_year,
            'ytd_current_year': 'YTD' + ' ' + self.date_to.strftime('%Y'),
            'ytd_pre_year': 'YTD' + ' ' + ytd_pre_year,
            None: None,
        }
        for key in column_keys:
            if isinstance(key, date):
                name = key.strftime('%b-%y')
            else:
                name = mapping_values.get(key)
            columns.append(name)
        return columns

    def _get_analytics_plans(self):
        return self.analytic_plan_ids

    def _get_all_plans(self):
        project_plan, _other_plans = self.env['account.analytic.plan']._get_all_plans()
        return (project_plan + _other_plans)

    def _get_all_plans_need(self):
        plans = self.analytic_plan_ids
        budget_allocation_ids = self.env['account.expense.allocation'].search([
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
            ('budget_id.state', 'in', ('confirm', 'validate', 'done')),
            ('to_analytic_plan_id', '!=', False),
            ('from_analytic_plan_ids', 'not in', [False, []])
        ])
        plans |= budget_allocation_ids.mapped('from_analytic_plan_ids')
        return plans

    def _column_keys(self):
        """
        columns structure:

        Business Unit 1 |  Business Unit 1  | Business Unit 2 | Business Unit 3 ... | TOTAL
        -----------------------------------------------------------------------------------
        return list of value included in ['clo1', record type, ..., None,
        """
        column_keys = ['col1']
        start_days_of_month = self._get_start_days()
        column_keys += [date for date in start_days_of_month]
        column_keys += ['total', None]
        column_keys += ['actual', 'budget', 'variant', 'variant_percent', None]
        column_keys += ['actual', 'budget', 'variant', 'variant_percent', None]
        column_keys += ['mtd_current_year', 'mtd_pre_year', 'variant', 'variant_percent', None]
        column_keys += ['ytd_current_year', 'ytd_pre_year', 'variant', 'variant_percent', None]
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

    def get_budget_amount_report_line(self, report_line, date_from_list):
        rates = self._get_currency_rates()
        budget_line_model = self.env['crossovered.budget.lines']
        struct_report = report_line.report_id
        budget_line_domain = [
            ('analytic_plan_id', 'in', self.analytic_plan_ids.ids)
        ]
        date_from_domain = osv.expression.OR([[('date_from', '=', date_from)] for date_from in date_from_list])
        budget_line_domain = osv.expression.AND([budget_line_domain, date_from_domain])

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
        expression_sum = round(expression_sum, struct_report.financial_report_currency.decimal_places)
        return expression_sum

    def _get_line_value_groupby_month_by_plan(self, report_line, plan_ids, first_day_of_months, date_from, date_to):
        struct_report = report_line.report_id
        report_currency = struct_report.financial_report_currency
        # plan_ids = self._get_analytics_plans()
        analytic_line_obj = self.env['account.analytic.line']
        aa_obj = self.env['account.analytic.account']
        currency_table_query = self.env['crossovered.budget.lines']._get_query_currency_table(
            self.env.company.ids, currency_id=report_currency, conversion_date=self.date_to.strftime('%Y-%m-%d'))
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ]
        analytic_domain = osv.expression.OR([
            [(f'{plan._column_name()}', 'in', aa_obj.search([('plan_id', "child_of", plan.id)]).ids)]
            for plan in plan_ids])
        if analytic_domain:
            domain = osv.expression.AND([domain, analytic_domain])
        result_groupby_month = defaultdict(lambda: 0.0)
        for expression in report_line.expression_ids.filtered(lambda x: x.engine == 'account_codes'):
            formula = expression.formula.replace(' ', '')
            account_list = ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(formula)
            account_list = [acc.replace('+', '').replace('-', '') for acc in account_list if acc]
            if account_list:
                domain += [('general_account_id.code', 'in', tuple(account_list))]
            else:
                raise UserError(_("The report line: %s - % does not contains valid accounting account!", report_line.code, report_line.name))

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
            query_result = self._cr.dictfetchall()
            sum_by_account_by_month = defaultdict(lambda: {key: 0.0 for key in account_list})
            for date_val in query_result:
                sum_by_account_by_month[date_val['date'].strftime('%Y-%m-%d')][str(date_val['account_code'])] += date_val['sum']

            for month_str, value_by_account in sum_by_account_by_month.items():
                formula = expression.formula.replace(' ', '')
                for account_code, value in value_by_account.items():
                    formula = re.sub(account_code, f'{value}', formula)
                result_groupby_month[month_str] += expr_eval(formula)
        results = {}
        # Change the key to object datetime.date
        for month in first_day_of_months:
            month_key = month.strftime('%Y-%m-%d')
            results[month] = round(
                result_groupby_month[month_key],   # Get abs() value
                report_line.report_id.financial_report_currency.decimal_places)
        return results

    def _compute_per_detail_lines(self, report_line, first_day_of_months):
        """"""
        default_from = self.date_from
        default_to = self.date_to

        single_lines = [0.0 for index in first_day_of_months]
        all_plans = self._get_all_plans_need()
        analytics_plans = self._get_analytics_plans()
        result_by_month = {}
        for plan in all_plans:
            amount_by_date_range_dict = self._get_line_value_groupby_month_by_plan(
                report_line, plan, first_day_of_months, default_from, default_to)
            result_by_month[plan] = amount_by_date_range_dict

        # Get single lines from 'result_by_date_range'
        for date_index in range(len(first_day_of_months)):
            for plan in analytics_plans:
                date_key = first_day_of_months[date_index]
                single_lines[date_index] += result_by_month[plan][date_key]
        total_of_line = sum(single_lines)
        single_lines.append(total_of_line)

        today = fields.Date.today()
        # Get balance actual MONTH TO DATE in the current year
        if default_to < today:
            mtd_from = date(day=1, month=default_to.month, year=default_to.year)
            mtd_to = date(day=calendar.monthrange(default_to.year, default_to.month)[1], month=default_to.month, year=default_to.year)
        else:
            mtd_from = date(day=1, month=today.month, year=default_to.year)
            mtd_to = date(day=calendar.monthrange(today.year, today.month)[1], month=today.month, year=today.year)
        mtd_result_by_month = {}
        for plan in all_plans:
            mtd_result_by_month[plan] = self._get_line_value_groupby_month_by_plan(
                report_line, plan, first_day_of_months, mtd_from, mtd_to)
        mtd_balance_curr_year = 0.0
        for plan in analytics_plans:
            date_key = mtd_from
            mtd_balance_curr_year += mtd_result_by_month[plan].get(date_key, 0.0)

        # Get balance actual YEAR TO DATE in the current year
        ytd_from = self.date_from.replace(day=1, month=1)
        ytd_to = default_to if default_to < today else date(year=default_to.year, month=today.month,  day=calendar.monthrange(default_to.year, month=today.month)[1])
        ytd_result_by_month = {}
        for plan in all_plans:
            ytd_result_by_month[plan] = self._get_line_value_groupby_month_by_plan(
                report_line, plan, first_day_of_months, ytd_from, ytd_to)
        ytd_balance_curr_year = 0.0
        for plan in analytics_plans:
            ytd_balance_curr_year += sum(ytd_result_by_month[plan].values())

        # Get budget month to date
        mtd_budget = self.get_budget_amount_report_line(report_line, [mtd_from])

        # Get budget year to date
        months_to_get_budget = [month for month in first_day_of_months if month.month <= today.month]
        ytd_budget = self.get_budget_amount_report_line(report_line, [*months_to_get_budget])

        # Get balance MONTH TO DATE in the previous year
        first_day_of_months_in_prev_year = [d.replace(year=d.year - 1) for d in first_day_of_months]
        if default_to.month < today.month:
            mtd_from_prev_year = date(day=1, month=default_to.month, year=default_to.year - 1)
            mtd_to_prev_year = date(day=calendar.monthrange(default_to.year - 1, default_to.month)[1],
                                    month=default_to.month, year=default_to.year - 1)
        else:
            mtd_from_prev_year = date(day=1, month=today.month, year=self.date_from.year - 1)
            mtd_to_prev_year = date(day=calendar.monthrange(default_to.year - 1, today.month)[1], month=today.month,
                                    year=self.date_from.year - 1)
        mtd_result_by_month_prev_year = {}
        for plan in all_plans:
            mtd_result_by_month_prev_year[plan] = self._get_line_value_groupby_month_by_plan(
                report_line, plan, first_day_of_months_in_prev_year, mtd_from_prev_year, mtd_to_prev_year)
        mtd_balance_prev_year = 0.0
        for plan in analytics_plans:
            date_key = mtd_from_prev_year
            mtd_balance_prev_year += mtd_result_by_month_prev_year[plan].get(date_key, 0.0)

        # Get balance actual YEAR TO DATE in the current year
        ytd_from_prev_year = date(day=1, month=1, year=self.date_from.year - 1)
        if default_to.month < today.month:
            ytd_to_prev_year = date(year=default_to.year-1, month=default_to.month, day=calendar.monthrange(default_to.year-1, default_to.month)[1])
        else:
            ytd_to_prev_year = date(year=default_to.year-1, month=today.month, day=calendar.monthrange(year=today.year, month=today.month)[1])
        ytd_result_by_month_prev_year = {}
        for plan in all_plans:
            ytd_result_by_month_prev_year[plan] = self._get_line_value_groupby_month_by_plan(
                report_line, plan, first_day_of_months_in_prev_year, ytd_from_prev_year, ytd_to_prev_year)
        ytd_balance_prev_year = 0.0
        for plan in analytics_plans:
            ytd_balance_prev_year += sum(ytd_result_by_month_prev_year[plan].values())

        # Compute Variant and Variant % compare with budget in the current year
        mtd_variant_curr_year = mtd_balance_curr_year - mtd_budget
        mtd_variant_percent_curr_year = round(mtd_variant_curr_year/abs(mtd_budget) * 100 if mtd_budget else 0.0, 2)

        ytd_variant_curr_year = ytd_balance_curr_year - ytd_budget
        ytd_variant_percent_curr_year = round(ytd_variant_curr_year/abs(ytd_budget) * 100 if ytd_budget else 0.0, 2)

        # Compare MTD balance with the previous year
        mtd_variant_prev_year = mtd_balance_curr_year - mtd_balance_prev_year
        mtd_variant_percent_prev_year = round(mtd_variant_prev_year/abs(mtd_balance_prev_year) * 100 if mtd_balance_prev_year else 0, 2)

        # Compare YTD balance with the previous year
        ytd_variant_prev_year = ytd_balance_curr_year - ytd_balance_prev_year
        ytd_variant_percent_prev_year = round(ytd_variant_prev_year/abs(ytd_balance_prev_year) * 100 if ytd_balance_prev_year else 0, 2)

        columns = [
            *single_lines,
            None,
            mtd_balance_curr_year,
            mtd_budget,
            mtd_variant_curr_year,
            mtd_variant_percent_curr_year,
            None,
            ytd_balance_curr_year,
            ytd_budget,
            ytd_variant_curr_year,
            ytd_variant_percent_curr_year,
            None,
            mtd_balance_curr_year,
            mtd_balance_prev_year,
            mtd_variant_prev_year,
            mtd_variant_percent_prev_year,
            None,
            ytd_balance_curr_year,
            ytd_balance_prev_year,
            ytd_variant_prev_year,
            ytd_variant_percent_prev_year,
        ]
        results = {
            'columns': columns,
            'result_by_month': result_by_month,
            'mtd_result_by_month': mtd_result_by_month,
            'ytd_result_by_month': ytd_result_by_month,
            'mtd_result_by_month_prev_year': mtd_result_by_month_prev_year,
            'ytd_result_by_month_prev_year': ytd_result_by_month_prev_year,
        }
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
        computing_col_keys = [
            'total', 'actual', 'budget', 'variant',
            'mtd_current_year', 'mtd_pre_year', 'ytd_current_year', 'ytd_pre_year'
        ]
        for col_index in range(len(column_keys)):
            column_key = column_keys[col_index]
            if isinstance(column_key, date) or column_key in computing_col_keys:
                expression_sum = 0.0
                for expression in report_line.expression_ids:
                    formula = expression.formula
                    terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                     term and not _check_is_float(term) and not keyword.iskeyword(term)]
                    for term in terms_to_eval:
                        if not value_lines_by_code.get(term):
                            raise UserError(_('The term of formula: %s is undefined' % term))
                        term_value = value_lines_by_code[term]['columns'][col_index]
                        formula = re.sub(term_replacement_regex % re.escape(term), f'({term_value})', formula)
                    try:
                        expression_sum += expr_eval(formula)  # Get abs() value
                    except ZeroDivisionError:
                        expression_sum += 0
                    except Exception as e:
                        raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))

                single_line_columns.append(
                    round(expression_sum, report_line.report_id.financial_report_currency.decimal_places))
            elif column_key == 'variant_percent':
                single_line_columns.append(None if not report_line.expression_ids else '%%%')
            else:
                single_line_columns.append(None)

        COLUMN_STEP = 5
        if report_line.expression_ids:
            number_of_months = len(list(filter(lambda x: isinstance(x, date), column_keys)))
            variant = single_line_columns[number_of_months + 4 + COLUMN_STEP * 0]
            denominator = single_line_columns[number_of_months + 3 + COLUMN_STEP * 0]
            variant_percent = round(variant / denominator * 100 if denominator else 0, 2)

            variant_2 = single_line_columns[number_of_months + 4 + COLUMN_STEP * 1]
            denominator_2 = single_line_columns[number_of_months + 3 + COLUMN_STEP * 1]
            variant_percent_2 = round(variant_2 / denominator_2 * 100 if denominator_2 else 0, 2)

            variant_3 = single_line_columns[number_of_months + 4 + COLUMN_STEP * 2]
            denominator_3 = single_line_columns[number_of_months + 3 + COLUMN_STEP * 2]
            variant_percent_3 = round(variant_3 / denominator_3 * 100 if denominator_3 else 0, 2)

            variant_4 = single_line_columns[number_of_months + 4 + COLUMN_STEP * 3]
            denominator_4 = single_line_columns[number_of_months + 3 + COLUMN_STEP * 3]
            variant_percent_4 = round(variant_4 / denominator_4 * 100 if denominator_4 else 0, 2)

            single_line_columns[number_of_months + 5 + COLUMN_STEP * 0] = variant_percent
            single_line_columns[number_of_months + 5 + COLUMN_STEP * 1] = variant_percent_2
            single_line_columns[number_of_months + 5 + COLUMN_STEP * 2] = variant_percent_3
            single_line_columns[number_of_months + 5 + COLUMN_STEP * 3] = variant_percent_4

        first_day_of_months_pre_year = [d.replace(year=d.year - 1) for d in first_day_of_months]
        all_plans = self._get_all_plans_need()
        result_by_month = defaultdict(lambda: {key: 0.0 for key in first_day_of_months})
        mtd_result_by_month = defaultdict(lambda: {key: 0.0 for key in first_day_of_months})
        ytd_result_by_month = defaultdict(lambda: {key: 0.0 for key in first_day_of_months})
        mtd_result_by_month_prev_year = defaultdict(lambda: {key: 0.0 for key in first_day_of_months_pre_year})
        ytd_result_by_month_prev_year = defaultdict(lambda: {key: 0.0 for key in first_day_of_months_pre_year})
        dict_key_list = ['result_by_month', 'mtd_result_by_month', 'ytd_result_by_month',
                         'mtd_result_by_month_prev_year', 'ytd_result_by_month_prev_year']
        for dict_key in dict_key_list:
            for plan in all_plans:
                if dict_key in ['mtd_result_by_month_prev_year', 'ytd_result_by_month_prev_year']:
                    first_day_of_months_real = first_day_of_months_pre_year
                else:
                    first_day_of_months_real = first_day_of_months
                for month in first_day_of_months_real:
                    exp_sum_in_month = 0.0
                    for expression in report_line.expression_ids:
                        formula = expression.formula
                        terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                         term and not _check_is_float(term) and not keyword.iskeyword(term)]
                        for term in terms_to_eval:
                            if not value_lines_by_code.get(term):
                                raise UserError(_('The term of formula: %s is undefined' % term))
                            term_value = value_lines_by_code[term][dict_key][plan][month]
                            formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                        try:
                            exp_sum_in_month += expr_eval(formula)
                        except ZeroDivisionError:
                            exp_sum_in_month += 0
                        except Exception as e:
                            raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
                    exp_sum_in_month = round(exp_sum_in_month, report_line.report_id.financial_report_currency.decimal_places)
                    eval(dict_key)[plan][month] = exp_sum_in_month
        results = {
            'columns': single_line_columns,
            'result_by_month': result_by_month,
            'mtd_result_by_month': mtd_result_by_month,
            'ytd_result_by_month': ytd_result_by_month,
            'mtd_result_by_month_prev_year': mtd_result_by_month_prev_year,
            'ytd_result_by_month_prev_year': ytd_result_by_month_prev_year
        }
        return results

    def _compute_per_allocation_lines(self, report_line, first_day_of_months, value_lines):
        def _check_is_float(to_test):
            try:
                float(to_test)
                return True
            except ValueError:
                return False

        today  = fields.Date.today()
        single_line_columns = []
        value_lines_by_code = {line.code or line.id: value for line, value in value_lines.items()}
        term_separator_regex = r'(?<!\de)[+-]|[ ()/*]'
        term_replacement_regex = r"(^|(?<=[ ()+/*-]))%s((?=[ ()+/*-])|$)"
        first_day_of_months_pre_year = [d.replace(year=d.year - 1) for d in first_day_of_months]
        result_by_month = defaultdict(lambda: {key: 0.0 for key in first_day_of_months})
        mtd_result_by_month = defaultdict(lambda: {key: 0.0 for key in first_day_of_months})
        ytd_result_by_month = defaultdict(lambda: {key: 0.0 for key in first_day_of_months})
        mtd_result_by_month_prev_year = defaultdict(lambda: {key: 0.0 for key in first_day_of_months_pre_year})
        ytd_result_by_month_prev_year = defaultdict(lambda: {key: 0.0 for key in first_day_of_months_pre_year})

        all_plans = self._get_all_plans_need()
        analytic_plans = self._get_analytics_plans()
        rate_by_date_ranges = self.get_alloc_rate_in_range_date()
        column_keys = self._column_keys()[1:]
        date_column_keys = list(filter(lambda x: isinstance(x, date), column_keys))
        mtd_balance_curr_year = 0
        ytd_balance_curr_year = 0
        mtd_balance_prev_year = 0
        ytd_balance_prev_year = 0

        for col_index in range(len(column_keys)):
            column_key = column_keys[col_index]

            key_of_value = None
            if column_key in date_column_keys:
                key_of_value = 'result_by_month'
            elif column_key == 'actual' and col_index == 14:
                key_of_value = 'mtd_result_by_month'
            elif column_key == 'actual' and col_index == 19:
                key_of_value = 'ytd_result_by_month'
            elif column_key == 'mtd_pre_year' and col_index == 29:
                key_of_value = 'mtd_result_by_month_prev_year'
            elif column_key == 'ytd_pre_year' and col_index == 24:
                key_of_value = 'ytd_result_by_month_prev_year'

            if column_key in date_column_keys:
                month = column_key
                column_sum = 0.0
                for expression in report_line.expression_ids:
                    formula = expression.formula
                    terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                     term and not _check_is_float(term) and not keyword.iskeyword(term)]
                    for term in terms_to_eval:
                        if not value_lines_by_code.get(term):
                            raise UserError(_('The term of formula: %s is undefined' % term))
                        term_value = 0.0
                        for plan in analytic_plans:
                            rate_data = self.get_rate_data(month, rate_by_date_ranges)
                            coeff = rate_data.get(plan, ([], 0.0))[1]
                            from_analytic_plan_ids = rate_data.get(plan, ([], 0.0))[0]
                            source_total_amount = 0.0
                            for src_plan in from_analytic_plan_ids:
                                source_total_amount += value_lines_by_code[term]['result_by_month'][src_plan][month]
                            if from_analytic_plan_ids and plan.id not in from_analytic_plan_ids.ids:
                                val = value_lines_by_code[term]['result_by_month'][plan].get(month, 0.0)
                                column_sum += val
                            term_value += source_total_amount * coeff / 100
                        formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                    try:
                        column_sum += expr_eval(formula)
                    except ZeroDivisionError:
                        column_sum += 0
                    except Exception as e:
                        raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
                column_sum = round(column_sum, report_line.report_id.financial_report_currency.decimal_places)
                single_line_columns.append(column_sum)

            elif key_of_value and key_of_value == 'mtd_result_by_month':
                mtd_balance_curr_year = 0.0
                mtd_from = date(day=1, month=today.month, year=self.date_from.year)
                for expression in report_line.expression_ids:
                    formula = expression.formula
                    terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                     term and not _check_is_float(term) and not keyword.iskeyword(term)]
                    for term in terms_to_eval:
                        if not value_lines_by_code.get(term):
                            raise UserError(_('The term of formula: %s is undefined' % term))
                        term_value = 0.0
                        for plan in analytic_plans:
                            rate_data = self.get_rate_data(month, rate_by_date_ranges)
                            coeff = rate_data.get(plan, ([], 0.0))[1]  # rate_by_date_ranges[month]
                            from_analytic_plan_ids = rate_data.get(plan, ([], 0.0))[0]
                            source_total_amount = 0.0
                            for src_plan in from_analytic_plan_ids:
                                source_total_amount += value_lines_by_code[term]['mtd_result_by_month'][src_plan][mtd_from]
                            term_value += source_total_amount * coeff / 100
                        formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                    try:
                        mtd_balance_curr_year += expr_eval(formula)
                    except ZeroDivisionError:
                        mtd_balance_curr_year += 0
                    except Exception as e:
                        raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
                mtd_balance_curr_year = round(mtd_balance_curr_year, report_line.report_id.financial_report_currency.decimal_places)

            elif key_of_value and key_of_value == 'mtd_result_by_month_prev_year':
                mtd_balance_prev_year = 0.0
                mtd_from_prev_year = date(day=1, month=today.month, year=self.date_from.year - 1)

                for expression in report_line.expression_ids:
                    formula = expression.formula
                    terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                     term and not _check_is_float(term) and not keyword.iskeyword(term)]
                    for term in terms_to_eval:
                        if not value_lines_by_code.get(term):
                            raise UserError(_('The term of formula: %s is undefined' % term))
                        term_value = 0.0
                        for plan in analytic_plans:
                            rate_data = self.get_rate_data(month, rate_by_date_ranges)
                            coeff = rate_data.get(plan, ([], 0.0))[1]  # rate_by_date_ranges[month]
                            from_analytic_plan_ids = rate_data.get(plan, ([], 0.0))[0]
                            source_total_amount = 0.0
                            for src_plan in from_analytic_plan_ids:
                                source_total_amount += value_lines_by_code[term][key_of_value][src_plan][mtd_from_prev_year]
                            term_value += source_total_amount * coeff / 100
                        formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                    try:
                        mtd_balance_prev_year += expr_eval(formula)
                    except ZeroDivisionError:
                        mtd_balance_prev_year += 0
                    except Exception as e:
                        raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
                mtd_balance_prev_year = round(mtd_balance_prev_year, report_line.report_id.financial_report_currency.decimal_places)

            elif key_of_value and key_of_value == 'ytd_result_by_month':
                ytd_balance_curr_year = 0.0
                first_day_of_months_real = first_day_of_months
                for mtd_from in first_day_of_months_real:
                    month_sum = 0.0
                    for expression in report_line.expression_ids:
                        formula = expression.formula
                        terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                         term and not _check_is_float(term) and not keyword.iskeyword(term)]
                        for term in terms_to_eval:
                            if not value_lines_by_code.get(term):
                                raise UserError(_('The term of formula: %s is undefined' % term))
                            term_value = 0.0
                            for plan in analytic_plans:
                                rate_data = self.get_rate_data(month, rate_by_date_ranges)
                                coeff = rate_data.get(plan, ([], 0.0))[1]  # rate_by_date_ranges[month]
                                from_analytic_plan_ids = rate_data.get(plan, ([], 0.0))[0]
                                source_total_amount = 0.0
                                for src_plan in from_analytic_plan_ids:
                                    source_total_amount += value_lines_by_code[term][key_of_value][src_plan][mtd_from]
                                term_value += source_total_amount * coeff / 100
                            formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                        try:
                            month_sum += expr_eval(formula)
                        except ZeroDivisionError:
                            month_sum += 0
                        except Exception as e:
                            raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
                    ytd_balance_curr_year += month_sum
                ytd_balance_curr_year = round(ytd_balance_curr_year, report_line.report_id.financial_report_currency.decimal_places)

            elif key_of_value and key_of_value == 'ytd_result_by_month_prev_year':
                ytd_balance_prev_year = 0.0
                first_day_of_months_real = first_day_of_months_pre_year
                for mtd_from in first_day_of_months_real:
                    month_sum = 0.0
                    for expression in report_line.expression_ids:
                        formula = expression.formula
                        terms_to_eval = [term for term in re.split(term_separator_regex, formula) if
                                         term and not _check_is_float(term) and not keyword.iskeyword(term)]
                        for term in terms_to_eval:
                            if not value_lines_by_code.get(term):
                                raise UserError(_('The term of formula: %s is undefined' % term))
                            term_value = 0.0
                            for plan in analytic_plans:
                                rate_data = self.get_rate_data(month, rate_by_date_ranges)
                                coeff = rate_data.get(plan, ([], 0.0))[1]  # rate_by_date_ranges[month]
                                from_analytic_plan_ids = rate_data.get(plan, ([], 0.0))[0]
                                source_total_amount = 0.0
                                for src_plan in from_analytic_plan_ids:
                                    source_total_amount += value_lines_by_code[term][key_of_value][src_plan][mtd_from]
                                term_value += source_total_amount * coeff / 100
                            formula = re.sub(term_replacement_regex % re.escape(term), f'{term_value}', formula)
                        try:
                            month_sum += expr_eval(formula)
                        except ZeroDivisionError:
                            month_sum += 0
                        except Exception as e:
                            raise UserError(_('Error while parsing the formula: %s \n %s', expression.formula, str(e)))
                    ytd_balance_prev_year += month_sum
                ytd_balance_prev_year = round(ytd_balance_prev_year, report_line.report_id.financial_report_currency.decimal_places)

        total_of_line = round(-sum(single_line_columns), report_line.report_id.financial_report_currency.decimal_places)
        single_line_columns.append(total_of_line)

        mtd_from = date(day=1, month=today.month, year=self.date_from.year)
        # Get budget month to date
        mtd_budget = self.get_budget_amount_report_line(report_line, [mtd_from])

        # Get budget year to date
        months_to_get_budget = [month for month in first_day_of_months if month <= mtd_from]
        ytd_budget = self.get_budget_amount_report_line(report_line, [*months_to_get_budget])

        # Compute Variant and Variant % compare with budget in the current year
        mtd_variant_curr_year = mtd_balance_curr_year - mtd_budget
        mtd_variant_percent_curr_year = round(mtd_variant_curr_year/abs(mtd_budget) * 100 if mtd_budget else 0.0, 2)

        ytd_variant_curr_year = ytd_balance_curr_year - ytd_budget
        ytd_variant_percent_curr_year = round(ytd_variant_curr_year/abs(ytd_budget) * 100 if ytd_budget else 0.0, 2)

        # Compare MTD balance with the previous year
        mtd_variant_prev_year = mtd_balance_curr_year - mtd_balance_prev_year
        mtd_variant_percent_prev_year = round(mtd_variant_prev_year/abs(mtd_balance_prev_year) * 100 if mtd_balance_prev_year else 0, 2)

        # Compare YTD balance with the previous year
        ytd_variant_prev_year = ytd_balance_curr_year - ytd_balance_prev_year
        ytd_variant_percent_prev_year = round(ytd_variant_prev_year/abs(ytd_balance_prev_year) * 100 if ytd_balance_prev_year else 0, 2)

        single_line_columns = [
            *single_line_columns,
            None,
            mtd_balance_curr_year,
            mtd_budget,
            mtd_variant_curr_year,
            mtd_variant_percent_curr_year,
            None,
            ytd_balance_curr_year,
            ytd_budget,
            ytd_variant_curr_year,
            ytd_variant_percent_curr_year,
            None,
            mtd_balance_curr_year,
            mtd_balance_prev_year,
            mtd_variant_prev_year,
            mtd_variant_percent_prev_year,
            None,
            ytd_balance_curr_year,
            ytd_balance_prev_year,
            ytd_variant_prev_year,
            ytd_variant_percent_prev_year,
        ]

        results = {
            'columns': single_line_columns,
            'result_by_month': result_by_month,
            'mtd_result_by_month': mtd_result_by_month,
            'ytd_result_by_month': ytd_result_by_month,
            'mtd_result_by_month_prev_year': mtd_result_by_month_prev_year,
            'ytd_result_by_month_prev_year': ytd_result_by_month_prev_year
        }
        return results

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
        before_compute_lines = structure_report.line_ids.filtered(lambda l: not l.compute_after)
        value_lines = {}
        # Detail line by account, report_line has 'expression_ids' and 'parent_id' don't have 'expression_ids'
        detail_line_ids = before_compute_lines.filtered(
            lambda l: l.expression_ids and l.parent_id and not l.parent_id.expression_ids and not l.reallocation_compute)
        for report_line in detail_line_ids:
            line_value = self._compute_per_detail_lines(report_line, first_day_of_months)
            value_lines[report_line] = line_value

        # Detail line by account groups, report_line has 'expression_ids' and parent_id don't have 'expression_ids'
        total_line_ids = before_compute_lines.filtered(lambda l: l.expression_ids and not l.parent_id and not l.reallocation_compute)
        for report_line in total_line_ids:
            line_value = self._compute_per_total_lines(report_line, first_day_of_months, value_lines)
            value_lines[report_line] = line_value

        reallocation_total_line_ids = before_compute_lines.filtered(lambda l: l.expression_ids and l.reallocation_compute)
        for report_line in reallocation_total_line_ids:
            line_value = self._compute_per_allocation_lines(report_line, first_day_of_months, value_lines)
            value_lines[report_line] = line_value

        after_compute_lines = structure_report.line_ids.filtered(lambda l: l.compute_after)
        for report_line in after_compute_lines:
            line_value = self._compute_per_total_lines(report_line, first_day_of_months, value_lines)
            value_lines[report_line] = line_value

        lines = []
        # Prepare static line
        for line in structure_report.line_ids.filtered(lambda li: '%' not in li.name):
            line_dict = self._get_static_line_dict(line, value_lines)
            lines.append(line_dict)

        column_keys = self._column_keys()
        subheaders = self._get_subheader_colums(column_keys)
        headers = self._get_header_colums(column_keys)

        return subheaders, headers, lines

    def _inject_report_into_xlsx_sheet(self, workbook, sheet):
        def write_with_colspan(sheet, x, y, value, colspan, style):
            if colspan == 1:
                sheet.write(y, x, value, style)
            else:
                sheet.merge_range(y, x, y, x + colspan - 1, value, style)

        empty_style = workbook.add_format({'font_name': 'Arial', 'bold': False, 'bottom': 0, 'top': 0})
        title_header_style = workbook.add_format({'align': 'center', 'font_name': 'Arial', 'bold': True, 'bottom': 1, 'top': 1})
        default_col1_style = workbook.add_format(
            {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True})
        level_0_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666',
             'num_format': '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'})
        level_0_style_var_green = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#008000'})
        level_0_style_var_red = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#FF0000'})
        level_1_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 1, 'font_color': '#666666'})
        level_2_col1_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_2_style = workbook.add_format(
            {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_3_col1_style = workbook.add_format(
            {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666',
                                             'num_format': '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'})
        level_3_style_var_red = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#FF0000'})
        level_3_style_var_green = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#008000'})
        #  Set the first column width to 30
        sheet.set_column(0, 0, 30)

        y_offset = 0
        x_offset = 0
        # Write title and name report first
        period_date_info = self.get_period_info()
        report_name = 'SOA - PROFIT & LOSS BY BU - %s' % ", ".join(self._get_analytics_plans().mapped("name"))

        subheader_columns, header_columns, lines = self._get_lines()
        write_with_colspan(sheet, x_offset, y_offset, report_name, 1, title_style)
        y_offset += 1
        write_with_colspan(sheet, x_offset, y_offset, period_date_info, 1, title_style)

        # Write subheaders
        for col_indx in range(0, len(subheader_columns)):
            col_val = subheader_columns[col_indx]
            colspan = col_val.get('colspan')
            if col_val.get('name'):
                write_with_colspan(sheet, x_offset + col_indx + 1, y_offset, col_val.get('name'), colspan, title_header_style)
                x_offset += colspan - 1
            else:
                write_with_colspan(sheet, x_offset + col_indx + 1, y_offset, '', 1, empty_style)

        sheet.set_column(1, len(header_columns) - 1, 10)

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
                    if header_columns[x] == 'Variant %':
                        if level == 0:
                            if lines[y]['columns'][x - x_offset] < 0:
                                _style = level_0_style_var_red
                            elif lines[y]['columns'][x - x_offset] > 0:
                                _style = level_0_style_var_green
                        else:
                            if lines[y]['columns'][x - x_offset] < 0:
                                _style = level_3_style_var_red
                            elif lines[y]['columns'][x - x_offset] > 0:
                                _style = level_3_style_var_green
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
                'PNLBUAllocationReport', self._name, self.id)
        }
