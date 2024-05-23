# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import models, _, fields, api
from odoo.tools import float_compare
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT
from collections import defaultdict
from datetime import timedelta

_logger = logging.getLogger(__name__)


class TrialBalanceVASCustomHandler(models.AbstractModel):
    _name = 'account.trial.balance.vas.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Trial Balance Custom Handler'


    # Onnet customize get line base on VAS (CoA 200)
    def _get_account_title_line(self, report, options, account, has_lines, eval_dict):
        line_columns = []
        for column in options['columns']:
            col_value = eval_dict[column['column_group_key']].get(column['expression_label'])
            col_expr_label = column['expression_label']
            value = None if col_value is None or (col_expr_label == 'amount_currency' and not account.currency_id) else col_value

            line_columns.append(report._build_column_dict(
                value,
                column,
                options=options,
                currency=account.currency_id if col_expr_label == 'amount_currency' else None,
            ))

        line_id = report._get_generic_line_id('account.account', account.id)
        is_in_unfolded_lines = any(
            report._get_res_id_from_line_id(line_id, 'account.account') == account.id
            for line_id in options.get('unfolded_lines')
        )
        return {
            'id': line_id,
            'name': f'{account.code} {account.name}',
            'columns': line_columns,
            'level': 1,
            'unfoldable': has_lines,
            'unfolded': has_lines and (is_in_unfolded_lines or options.get('unfold_all')),
            'expand_function': '_report_expand_unfoldable_line_general_ledger',
        }

    @api.model
    def _get_total_line(self, report, options, eval_dict):
        line_columns = []
        for column in options['columns']:
            col_value = eval_dict[column['column_group_key']].get(column['expression_label'])
            col_value = None if col_value is None else col_value

            line_columns.append(report._build_column_dict(col_value, column, options=options))
        return {
            'id': report._get_generic_line_id(None, None, markup='total'),
            'name': _('Total'),
            'level': 1,
            'columns': line_columns,
        }

    def _get_options_unaffected_earnings(self, options):
        ''' Create options used to compute the unaffected earnings.
        The unaffected earnings are the amount of benefits/loss that have not been allocated to
        another account in the previous fiscal years.
        The resulting dates domain will be:
        [
          ('date' <= fiscalyear['date_from'] - 1),
          ('account_id.include_initial_balance', '=', False),
        ]
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        new_options.pop('filter_search_bar', None)
        fiscalyear_dates = self.env.company.compute_fiscalyear_dates(fields.Date.from_string(options['date']['date_from']))

        # Trial balance uses the options key, general ledger does not
        new_date_to = fields.Date.from_string(new_options['date']['date_to']) if options.get('include_current_year_in_unaff_earnings') else fiscalyear_dates['date_from'] - timedelta(days=1)

        new_options['date'] = {
            'mode': 'single',
            'date_to': fields.Date.to_string(new_date_to),
        }

        return new_options
    
    def _get_options_sum_balance(self, options):
        new_options = options.copy()

        if not options.get('general_ledger_strict_range'):
            # Date from
            date_from = fields.Date.from_string(new_options['date']['date_from'])
            current_fiscalyear_dates = self.env.company.compute_fiscalyear_dates(date_from)
            new_date_from = current_fiscalyear_dates['date_from']

            new_date_to = new_options['date']['date_to']

            new_options['date'] = {
                'mode': 'range',
                'date_from': fields.Date.to_string(new_date_from),
                'date_to': new_date_to,
            }

        return new_options
    
    def _get_query_sums(self, report, options):
        """ Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for VAS(200) accounts.
        - sums for the initial balances.
        - sums for the unaffected earnings.
        - sums for the tax declaration.
        :return:                    (query, params)
        """
        options_by_column_group = report._split_options_per_column_group(options)

        params = []
        queries = []

        # Create the currency table.
        # As the currency table is the same whatever the comparisons, create it only once.
        ct_query = report._get_query_currency_table(options)

        # ============================================
        # 1) Get sums for VAS (200) accounts.
        # ============================================
        for column_group_key, options_group in options_by_column_group.items():
            if not options.get('general_ledger_strict_range'):
                options_group = self._get_options_sum_balance(options_group)

            # Sum is computed including the initial balance of the accounts configured to do so, unless a special option key is used
            # (this is required for trial balance, which is based on general ledger)
            sum_date_scope = 'strict_range' if options_group.get('general_ledger_strict_range') else 'normal'

            query_domain = []

            # FIXME: redundant code or need to be refactored???
            # if options.get('export_mode') == 'print' and options.get('filter_search_bar'):
            #     query_domain.append(('account_id', 'ilike', options['filter_search_bar']))

            if options_group.get('include_current_year_in_unaff_earnings'):
                query_domain += [('account_id.include_initial_balance', '=', True)]

            tables, where_clause, where_params = report._query_get(options_group, sum_date_scope, domain=query_domain)
            params.append(column_group_key)
            params += where_params
            queries.append(f"""
                SELECT
                    account_move_line.account_id                            AS groupby,
                    'sum'                                                   AS key,
                    MAX(account_move_line.date)                             AS max_date,
                    %s                                                      AS column_group_key,
                    account_move_line.partner_id                            AS partner_id,
                    COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                    SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                    SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                    SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                FROM {tables}
                LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
                WHERE {where_clause}
                GROUP BY account_move_line.account_id, account_move_line.partner_id
            """)

            # ============================================
            # 2) Get sums for the unaffected earnings.
            # ============================================
            if not options_group.get('general_ledger_strict_range'):
                unaff_earnings_domain = [('account_id.include_initial_balance', '=', False)]

                # The period domain is expressed as:
                # [
                #   ('date' <= fiscalyear['date_from'] - 1),
                #   ('account_id.include_initial_balance', '=', False),
                # ]

                new_options = self._get_options_unaffected_earnings(options_group)
                tables, where_clause, where_params = report._query_get(new_options, 'strict_range', domain=unaff_earnings_domain)
                params.append(column_group_key)
                params += where_params
                queries.append(f"""
                    SELECT
                        account_move_line.company_id                            AS groupby,
                        'unaffected_earnings'                                   AS key,
                        NULL                                                    AS max_date,
                        %s                                                      AS column_group_key,
                        account_move_line.partner_id                            AS partner_id,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM {tables}
                    LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
                    WHERE {where_clause}
                    GROUP BY account_move_line.company_id, account_move_line.partner_id
                """)

        return ' UNION ALL '.join(queries), params

    def _query_values(self, report, options):
        """ Executes the queries, and performs all the computations.

        :return:    [(record, values_by_column_group), ...],  where
                    - record is an account.account record.
                    - values_by_column_group is a dict in the form {column_group_key: values, ...}
                        - column_group_key is a string identifying a column group, as in options['column_groups']
                        - values is a list of dictionaries, one per period containing:
                            - sum:                              {'debit': float, 'credit': float, 'balance': float}
                            - (optional) initial_balance:       {'debit': float, 'credit': float, 'balance': float}
                            - (optional) unaffected_earnings:   {'debit': float, 'credit': float, 'balance': float}
        """
        # Execute the queries and dispatch the results.
        query, params = self._get_query_sums(report, options)
        if not query:
            return []

        groupby_accounts = {}
        groupby_companies = {}
        self._cr.execute(query, params)
        for res in self._cr.dictfetchall():
            # No result to aggregate.
            if res['groupby'] is None:
                continue

            column_group_key = res['column_group_key']
            key = res['key']
            ##################################
                #VAS 200: NEED UPDATE 
            ########### start ################
            if key == 'sum':
                groupby_accounts.setdefault(res['groupby'], {col_group_key: {} for col_group_key in options['column_groups']})
                partner_id = res.pop('partner_id', None)
                if key not in groupby_accounts[res['groupby']][column_group_key]:
                    res.update({'partner_ids': [{
                        'partner_id': partner_id, 
                        'amount_currency': res['amount_currency'], 
                        'debit':res['debit'], 
                        'credit': res['credit'], 
                        'balance': res['balance']}], 
                    })
                    groupby_accounts[res['groupby']][column_group_key][key] = res
                else:
                    sum_val = groupby_accounts[res['groupby']][column_group_key][key]
                    for partner_val in sum_val['partner_ids']:
                        # update exisited partner
                        if partner_val['partner_id'] == partner_id:
                            partner_val.update({
                                'amount_currency': partner_val['amount_currency'] + res['amount_currency'],
                                'debit': partner_val['debit'] + res['debit'],
                                'credit': partner_val['credit'] + res['credit'],
                                'balance': partner_val['balance'] + res['balance'],
                            })
                            break
                        need_add_new = True
                    if need_add_new:
                        # add new partner if not exisited
                        sum_val['partner_ids'].append({
                            'partner_id': partner_id,
                            'amount_currency': res['amount_currency'],
                            'debit': res['debit'],
                            'credit': res['credit'],
                            'balance': res['balance'],
                        })
                    groupby_accounts[res['groupby']][column_group_key][key].update({
                        'max_date': res['max_date'] > sum_val['max_date'] and res['max_date'] or sum_val['max_date'],
                        'amount_currency': sum_val['amount_currency'] + res['amount_currency'],
                        'debit': sum_val['debit'] + res['debit'],
                        'credit': sum_val['credit'] + res['credit'],
                        'balance': sum_val['balance'] + res['balance'],
                        'partner_ids': sum_val['partner_ids']
                    })
            # TODO: debug for key in ['initial_balance','unaffected_earnings']
            elif key == 'initial_balance':
                groupby_accounts.setdefault(res['groupby'], {col_group_key: {} for col_group_key in options['column_groups']})
                groupby_accounts[res['groupby']][column_group_key][key] = res

            elif key == 'unaffected_earnings':
                groupby_companies.setdefault(res['groupby'], {col_group_key: {} for col_group_key in options['column_groups']})
                groupby_companies[res['groupby']][column_group_key] = res
                
            ########## end of customize vas 200 ##############
        # Affect the unaffected earnings to the first fetched account of type 'account.data_unaffected_earnings'.
        # There is an unaffected earnings for each company but it's less costly to fetch all candidate accounts in
        # a single search and then iterate it.
        if groupby_companies:
            candidates_account_ids = self.env['account.account']._name_search(options.get('filter_search_bar'), [
                *self.env['account.account']._check_company_domain(list(groupby_companies.keys())),
                ('account_type', '=', 'equity_unaffected'),
            ])
            for account in self.env['account.account'].browse(candidates_account_ids):
                company_unaffected_earnings = groupby_companies.get(account.company_id.id)
                if not company_unaffected_earnings:
                    continue
                for column_group_key in options['column_groups']:
                    unaffected_earnings = company_unaffected_earnings[column_group_key]
                    groupby_accounts.setdefault(account.id, {col_group_key: {} for col_group_key in options['column_groups']})
                    groupby_accounts[account.id][column_group_key]['unaffected_earnings'] = unaffected_earnings
                del groupby_companies[account.company_id.id]

        # Retrieve the accounts to browse.
        # groupby_accounts.keys() contains all account ids affected by:
        # - the amls in the current period.
        # - the amls affecting the initial balance.
        # - the unaffected earnings allocation.
        # Note a search is done instead of a browse to preserve the table ordering.
        if groupby_accounts:
            accounts = self.env['account.account'].search([('id', 'in', list(groupby_accounts.keys()))])
        else:
            accounts = []
        return [(account, groupby_accounts[account.id]) for account in accounts]

    def _vas200_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        lines = []
        date_from = fields.Date.from_string(options['date']['date_from'])
        company_currency = self.env.company.currency_id

        totals_by_column_group = defaultdict(lambda: {'debit': 0, 'credit': 0, 'balance': 0})
        for account, column_group_results in self._query_values(report, options):
            eval_dict = {}
            has_lines = False
            for column_group_key, results in column_group_results.items():
                account_sum = results.get('sum', {})
                account_un_earn = results.get('unaffected_earnings', {})
                # VAS 200 update debit/credit/balance groupby partner if account is follow by partner
                if account.follow_by_partner and ('initial_balance' in column_group_key or 'end_balance' in column_group_key):
                    account_debit = 0.0
                    account_credit = 0.0
                    for partner_val in account_sum.get('partner_ids',[]):
                        # tk mang tính chất lưỡng tính hiển thị ở cột có giá trị lớn hơn với công thức là debit - credit
                        amount_in_period = partner_val.get('debit',0.0) - partner_val.get('credit',0.0)
                        if amount_in_period >= 0:
                            account_debit += amount_in_period
                        else:
                            account_credit += abs(amount_in_period)
                    account_debit += account_un_earn.get('debit', 0.0)
                    account_credit += account_un_earn.get('credit', 0.0)
                    account_balance = account_sum.get('balance', 0.0) + account_un_earn.get('balance', 0.0)
                else:
                    account_debit = account_sum.get('debit', 0.0) + account_un_earn.get('debit', 0.0)
                    account_credit = account_sum.get('credit', 0.0) + account_un_earn.get('credit', 0.0)
                    account_balance = account_sum.get('balance', 0.0) + account_un_earn.get('balance', 0.0)

                eval_dict[column_group_key] = {
                    'amount_currency': account_sum.get('amount_currency', 0.0) + account_un_earn.get('amount_currency', 0.0),
                    'debit': account_debit,
                    'credit': account_credit,
                    'balance': account_balance,
                }

                max_date = account_sum.get('max_date')
                has_lines = has_lines or (max_date and max_date >= date_from)

                totals_by_column_group[column_group_key]['debit'] += account_debit
                totals_by_column_group[column_group_key]['credit'] += account_credit
                totals_by_column_group[column_group_key]['balance'] += account_balance

            lines.append(self._get_account_title_line(report, options, account, has_lines, eval_dict))
        # Report total line.
        for totals in totals_by_column_group.values():
            totals['balance'] = company_currency.round(totals['balance'])

        # Tax Declaration lines.
        journal_options = report._get_options_journals(options)
        if len(options['column_groups']) == 1 and len(journal_options) == 1 and journal_options[0]['type'] in ('sale', 'purchase'):
            lines += self._tax_declaration_lines(report, options, journal_options[0]['type'])

        # Total line
        lines.append(self._get_total_line(report, options, totals_by_column_group))
        return [(0, line) for line in lines]

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        def _update_column(line, column_key, new_value, blank_if_zero=False):
            line['columns'][column_key]['name'] = self.env['account.report']._format_value(options, new_value, figure_type='monetary', blank_if_zero=blank_if_zero)
            line['columns'][column_key]['no_format'] = new_value
        
        def _update_balance_columns(line, debit_column_key, credit_column_key, total_diff_values_key):
            debit_value = line['columns'][debit_column_key]['no_format'] if debit_column_key is not None else False
            credit_value = line['columns'][credit_column_key]['no_format'] if credit_column_key is not None else False

            if debit_value and credit_value:
                new_debit_value = 0.0
                new_credit_value = 0.0

                if float_compare(debit_value, credit_value, precision_digits=self.env.company.currency_id.decimal_places) == 1:
                    new_debit_value = debit_value - credit_value
                    total_diff_values[total_diff_values_key] += credit_value
                else:
                    new_credit_value = (debit_value - credit_value) * -1
                    total_diff_values[total_diff_values_key] += debit_value

                _update_column(line, debit_column_key, new_debit_value)
                _update_column(line, credit_column_key, new_credit_value)

        lines = [line[1] for line in self._vas200_lines_generator(report, options, all_column_groups_expression_totals, warnings=warnings)]
        total_diff_values = {
            'initial_balance': 0.0,
            'end_balance': 0.0,
        }
        
        # We need to find the index of debit and credit columns for initial and end balance in case of extra custom columns
        init_balance_debit_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'debit'), None)
        init_balance_credit_index = next((index for index, column in enumerate(options['columns']) if column.get('expression_label') == 'credit'), None)

        end_balance_debit_index = -(next((index for index, column in enumerate(reversed(options['columns'])) if column.get('expression_label') == 'debit'), -1) + 1)\
                                  or None
        end_balance_credit_index = -(next((index for index, column in enumerate(reversed(options['columns'])) if column.get('expression_label') == 'credit'), -1) + 1)\
        #                            or None
        for line in lines[:-1]:
            
            res_model = report._get_model_info_from_id(line['id'])[0]
            if res_model == 'account.account':
                account_account = self.env[res_model].browse(report._get_model_info_from_id(line['id'])[1])
                if account_account and not account_account.follow_by_partner: 
                    # Initial balance
                    _update_balance_columns(line, init_balance_debit_index, init_balance_credit_index, 'initial_balance')

                    # End balance
                    _update_balance_columns(line, end_balance_debit_index, end_balance_credit_index, 'end_balance')

            line.pop('expand_function', None)
            line.pop('groupby', None)
            line.update({
                'unfoldable': False,
                'unfolded': False,
            })

            res_model = report._get_model_info_from_id(line['id'])[0]
            if res_model == 'account.account':
                line['caret_options'] = 'trial_balance'

        # Total line
        if lines:
            total_line = lines[-1]

            for index, balance_key in zip(
                    (init_balance_debit_index, init_balance_credit_index, end_balance_debit_index, end_balance_credit_index),
                    ('initial_balance', 'initial_balance', 'end_balance', 'end_balance')
            ):
                if index is not None:
                    _update_column(total_line, index, total_line['columns'][index]['no_format'] - total_diff_values[balance_key], blank_if_zero=False)

        return [(0, line) for line in lines]

    def _caret_options_initializer(self):
        # TODO: VAS 200: change action to VAS General Ledger
        return {
            'trial_balance': [
                {'name': _("General Ledger"), 'action': 'caret_option_open_general_ledger'},
                {'name': _("Journal Items"), 'action': 'open_journal_items'},
            ],
        }

    def _custom_options_initializer(self, report, options, previous_options=None):
        """ Modifies the provided options to add a column group for initial balance and end balance, as well as the appropriate columns.
        """
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        default_group_vals = {'horizontal_groupby_element': {}, 'forced_options': {}}

        # Columns between initial and end balance must not include initial balance; we use a special option key for that in general ledger
        for column_group in options['column_groups'].values():
            column_group['forced_options']['general_ledger_strict_range'] = True

        if options['comparison']['periods']:
            # Reverse the order the group of columns with the same column_group_key while keeping the original order inside the group
            new_columns_order = []
            current_column = []
            current_column_group_key = options['columns'][-1]['column_group_key']

            for column in reversed(options['columns']):
                if current_column_group_key != column['column_group_key']:
                    current_column_group_key = column['column_group_key']
                    new_columns_order += current_column
                    current_column = []

                current_column.insert(0, column)
            new_columns_order += current_column

            options['columns'] = new_columns_order
            options['column_headers'][0][:] = reversed(options['column_headers'][0])

        # Initial balance
        initial_balance_options = self.env['account.general.ledger.report.handler']._get_options_initial_balance(options)
        initial_forced_options = {
            'date': initial_balance_options['date'],
            'initial_balance': True,
            'include_current_year_in_unaff_earnings': initial_balance_options['include_current_year_in_unaff_earnings']
        }
        initial_header_element = [{'name': _("Initial Balance"), 'forced_options': initial_forced_options}]
        col_headers_initial = [
            initial_header_element,
            *options['column_headers'][1:],
        ]
        initial_column_group_vals = report._generate_columns_group_vals_recursively(col_headers_initial, default_group_vals)
        initial_columns, initial_column_groups = report._build_columns_from_column_group_vals(initial_forced_options, initial_column_group_vals)

        # End balance
        end_date_to = options['date']['date_to']
        end_date_from = options['comparison']['periods'][-1]['date_from'] if options['comparison']['periods'] else options['date']['date_from']
        end_forced_options = {
            'end_balance': True,
            'date': {
                'mode': 'range',
                'date_to': fields.Date.from_string(end_date_to).strftime(DEFAULT_SERVER_DATE_FORMAT),
                'date_from': fields.Date.from_string(end_date_from).strftime(DEFAULT_SERVER_DATE_FORMAT)
            }
        }
        end_header_element = [{'name': _("End Balance"), 'forced_options': end_forced_options}]
        col_headers_end = [
            end_header_element,
            *options['column_headers'][1:],
        ]
        end_column_group_vals = report._generate_columns_group_vals_recursively(col_headers_end, default_group_vals)
        end_columns, end_column_groups = report._build_columns_from_column_group_vals(end_forced_options, end_column_group_vals)

        # Update options
        options['column_headers'][0] = initial_header_element + options['column_headers'][0] + end_header_element
        options['column_groups'].update(initial_column_groups)
        options['column_groups'].update(end_column_groups)
        options['columns'] = initial_columns + options['columns'] + end_columns
        options['ignore_totals_below_sections'] = True # So that GL does not compute them

        report._init_options_order_column(options, previous_options)

    def _custom_line_postprocessor(self, report, options, lines, warnings=None):
        # If the hierarchy is enabled, ensure to add the o_account_coa_column_contrast class to the hierarchy lines
        if options.get('hierarchy'):
            for line in lines:
                model, dummy = report._get_model_info_from_id(line['id'])
                if model == 'account.group':
                    line_classes = line.get('class', '')
                    line['class'] = line_classes + ' o_account_coa_column_contrast_hierarchy'
                    # customize debit/credit of group
                    eval_dict = {}
                    for column in line['columns']:
                        if column['column_group_key'] not in eval_dict:
                            eval_dict[column['column_group_key']] = {
                                column['expression_label']: float(column['no_format'])
                            }
                        else:
                            eval_dict[column['column_group_key']].update({
                                column['expression_label']: float(column['no_format'])
                            })
                    for column_group, dict_val in eval_dict.items():
                        balance = dict_val.get('debit', 0.0) - dict_val.get('credit', 0.0)
                        expr_label = 'debit' if balance > 0 else 'credit'
                        for col in filter(lambda x: x['column_group_key'] == column_group, line['columns']):
                            if col['expression_label'] == expr_label:
                                col.update({
                                    'no_format': balance > 0 and balance or balance * -1,
                                    'name': report.format_value(
                                        options,
                                        balance > 0 and balance or balance * -1,
                                        currency=col.get('currency'),
                                        blank_if_zero=col.get('blank_if_zero'),
                                        figure_type=col.get('figure_type'),
                                        digits=col.get('digits'))
                                })
                            else:
                                col.update({
                                    'no_format': 0.0,
                                    'name': 0
                                })
        return lines
    