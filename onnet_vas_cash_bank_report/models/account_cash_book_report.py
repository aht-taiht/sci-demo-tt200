# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _, fields, api
from odoo.tools import format_date, date_utils, get_lang
from collections import defaultdict


class CashBookReportCustomHandler(models.AbstractModel):
    _name = 'account.cash.book.report.handler'
    _inherit = 'account.general.ledger.report.handler'
    _description = 'Cash Book Report Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        options.update({
            'unfold_all': True
        })

        lines = []
        date_from = fields.Date.from_string(options['date']['date_from'])
        company_currency = self.env.company.currency_id

        totals_by_column_group = defaultdict(lambda: {'balance': 0})
        for account, column_group_results in self._query_values(report, options):
            eval_dict = {}
            has_lines = False
            for column_group_key, results in column_group_results.items():
                account_sum = results.get('sum', {})
                account_un_earn = results.get('unaffected_earnings', {})
                account_balance = account_sum.get('balance', 0.0) + account_un_earn.get('balance', 0.0)

                eval_dict[column_group_key] = {
                    'balance': account_balance,
                }

                max_date = account_sum.get('max_date')
                has_lines = has_lines or (max_date and max_date >= date_from)
                if has_lines:
                    totals_by_column_group[column_group_key]['balance'] += account_balance
                    eval_dict[column_group_key] = {
                        'balance': '',
                    }
                    lines.append(self._get_account_title_line(report, options, account, has_lines, eval_dict))

        # Report total line.
        for totals in totals_by_column_group.values():
            totals['balance'] = company_currency.round(totals['balance'])

        # Total line
        lines.append(self._get_total_line(report, options, totals_by_column_group))

        return [(0, line) for line in lines]

    def _report_expand_unfoldable_line_general_ledger(self, line_dict_id, groupby, options, progress, offset,
                                                      xml_id=None, unfold_all_batch_data=None):
        def init_load_more_progress(line_dict):
            return {
                column['column_group_key']: line_col.get('no_format', 0)
                for column, line_col in zip(options['columns'], line_dict['columns'])
                if column['expression_label'] == 'balance'
            }

        def get_initial_balance_line(report, options, parent_line_id, eval_dict,
                                     account_currency=None, level_shift=0,
                                     is_starting_balance=True):
            """ Helper to generate dynamic 'initial balance' lines, used by general ledger and partner ledger.
            """
            line_columns = []
            for column in options['columns']:
                col_value = eval_dict[column['column_group_key']].get(column['expression_label'])
                col_expr_label = column['expression_label']

                if col_value is None or (col_expr_label == 'amount_currency' and not account_currency):
                    line_columns.append(report._build_column_dict(None, None))
                elif col_expr_label == 'debit':
                    line_columns.append(report._build_column_dict(None, None))
                elif col_expr_label == 'credit':
                    col_value = _('Starting Balance:') if is_starting_balance else _('Ending Balance:')
                    line_columns.append(report._build_column_dict(
                        col_value,
                        column,
                        options=options,
                        currency=account_currency if col_expr_label == 'amount_currency' else None,
                    ))
                else:
                    line_columns.append(report._build_column_dict(
                        col_value,
                        column,
                        options=options,
                        currency=account_currency if col_expr_label == 'amount_currency' else None,
                    ))

            if not any(column.get('no_format') for column in line_columns):
                return None

            return {
                'id': report._get_generic_line_id(None, None, parent_line_id=parent_line_id,
                                                  markup='initial' if is_starting_balance else 'final'),
                'name': "",
                'level': 3 + level_shift,
                'parent_id': parent_line_id,
                'columns': line_columns,
            }

        if xml_id is None:
            xml_id = 'onnet_vas_cash_bank_report.cash_book_report'
        report = self.env.ref(xml_id)
        model, model_id = report._get_model_info_from_id(line_dict_id)
        lines = []
        # Get initial balance
        if offset == 0:
            account, init_balance_by_col_group = self._get_initial_balance_values(report, [model_id], options)[
                model_id]

            initial_balance_line = get_initial_balance_line(report, options, line_dict_id, init_balance_by_col_group,
                                                            account.currency_id)
            if initial_balance_line:
                lines.append(initial_balance_line)
                # For the first expansion of the line, the initial balance line gives the progress
                progress = init_load_more_progress(initial_balance_line)

        # Get move lines
        limit_to_load = report.load_more_limit + 1 if report.load_more_limit and options['export_mode'] != 'print' \
            else None
        has_more = False

        aml_results, has_more = self._get_aml_values(report, options, [model_id], offset=offset,
                                                     limit=limit_to_load)
        aml_results = aml_results[model_id]

        next_progress = progress

        for aml_result in aml_results.values():
            new_line = self._get_aml_line(report, line_dict_id, options, aml_result, next_progress)
            lines.append(new_line)
            next_progress = init_load_more_progress(new_line)

        # add ending balance
        if lines:
            # get last balance
            ending_balance = 0
            for column in lines[-1]['columns']:
                col_expr_label = column['expression_label']
                if col_expr_label == 'balance':
                    ending_balance = column['no_format']

            new_options = options.copy()
            ending_balance_by_col_group = init_balance_by_col_group.copy()
            for key, value in ending_balance_by_col_group.items():
                if 'balance' in ending_balance_by_col_group[key]:
                    ending_balance_by_col_group[key].update({'balance': ending_balance})
            ending_line = get_initial_balance_line(report, new_options, line_dict_id, ending_balance_by_col_group,
                                                   account.currency_id, is_starting_balance=False)
            if ending_line:
                lines.append(ending_line)

        return {
            'lines': lines,
            'offset_increment': report.load_more_limit,
            'has_more': has_more,
            'progress': next_progress,
        }

    def _custom_line_postprocessor(self, report, options, lines, warnings=None):
        """
            - Postprocesses the result of the report's _get_lines() before returning it.
            - Custom to remove total balance at ending line of account_group
        """
        new_lines = []
        for line in lines:
            if line.get('level', 0) == 1 and line.get('parent_id') and 'Total ' in line.get('name', ''):
                line.update({
                    'name': ''
                })
            else:
                new_lines.append(line)
        return new_lines

    def _get_query_sums(self, report, options, account_ids=[]):
        """ Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for all accounts.
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
        # 1) Get sums for all accounts.
        # ============================================
        for column_group_key, options_group in options_by_column_group.items():
            if not options.get('general_ledger_strict_range'):
                options_group = self._get_options_sum_balance(options_group)

            # Sum is computed including the initial balance of the accounts configured to do so, unless a special option key is used
            # (this is required for trial balance, which is based on general ledger)
            sum_date_scope = 'strict_range' if options_group.get('general_ledger_strict_range') else 'normal'

            if not account_ids:
                account_objs = self.env['account.account'].search([
                    ('code', '=ilike', '111%'), ('account_type', '=', 'asset_cash')])
                account_ids = account_objs.ids
            if len(account_ids) == 1:
                account_ids.append(9999999)

            query_domain = []

            if options.get('filter_search_bar'):
                query_domain.append(('account_id', 'ilike', options['filter_search_bar']))

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
                    COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                    SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                    SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                    SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                FROM {tables}
                LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                JOIN account_account aa on aa.id = account_move_line.account_id and aa.id in {tuple(account_ids)}
                WHERE {where_clause}
                GROUP BY account_move_line.account_id
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
                tables, where_clause, where_params = report._query_get(new_options, 'strict_range',
                                                                       domain=unaff_earnings_domain)
                params.append(column_group_key)
                params += where_params
                queries.append(f"""
                    SELECT
                        account_move_line.company_id                            AS groupby,
                        'unaffected_earnings'                                   AS key,
                        NULL                                                    AS max_date,
                        %s                                                      AS column_group_key,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM {tables}
                    LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                    JOIN account_account aa on aa.id = account_move_line.account_id and aa.id in {tuple(account_ids)}
                    WHERE {where_clause}
                    GROUP BY account_move_line.company_id
                """)

        return ' UNION ALL '.join(queries), params

    def _get_query_amls(self, report, options, expanded_account_ids, offset=0, limit=None):
        """ Construct a query retrieving the account.move.lines when expanding a report line with or without the load
        more.
        :param options:               The report options.
        :param expanded_account_ids:  The account.account ids corresponding to consider. If None, match every account.
        :param offset:                The offset of the query (used by the load more).
        :param limit:                 The limit of the query (used by the load more).
        :return:                      (query, params)
        """
        additional_domain = [('account_id', 'in', expanded_account_ids)] if expanded_account_ids is not None else None
        queries = []
        all_params = []
        lang = self.env.user.lang or get_lang(self.env).code
        journal_name = f"COALESCE(journal.name->>'{lang}', journal.name->>'en_US')" if \
            self.pool['account.journal'].name.translate else 'journal.name'
        account_name = f"COALESCE(account.name->>'{lang}', account.name->>'en_US')" if \
            self.pool['account.account'].name.translate else 'account.name'
        for column_group_key, group_options in report._split_options_per_column_group(options).items():
            # Get sums for the account move lines.
            # period: [('date' <= options['date_to']), ('date', '>=', options['date_from'])]
            tables, where_clause, where_params = report._query_get(
                group_options, domain=additional_domain, date_scope='strict_range')
            ct_query = report._get_query_currency_table(group_options)
            query = f'''
                (SELECT
                    account_move_line.id,
                    account_move_line.date,
                    account_move_line.date_maturity,
                    account_move_line.name,
                    account_move_line.ref,
                    account_move_line.offset_account,
                    account_move_line.company_id,
                    account_move_line.account_id,
                    account_move_line.payment_id,
                    account_move_line.partner_id,
                    account_move_line.currency_id,
                    account_move_line.amount_currency,
                    COALESCE(account_move_line.invoice_date, account_move_line.date)                 AS invoice_date,
                    ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                    ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                    ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance,
                    move.name                               AS move_name,
                    company.currency_id                     AS company_currency_id,
                    partner.name                            AS partner_name,
                    move.move_type                          AS move_type,
                    account.code                            AS account_code,
                    {account_name}                          AS account_name,
                    journal.code                            AS journal_code,
                    {journal_name}                          AS journal_name,
                    full_rec.id                             AS full_rec_name,
                    %s                                      AS column_group_key
                FROM {tables}
                JOIN account_move move                      ON move.id = account_move_line.move_id
                LEFT JOIN {ct_query}                        ON currency_table.company_id = account_move_line.company_id
                LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
                WHERE {where_clause}
                ORDER BY account_move_line.date, account_move_line.id)
            '''

            queries.append(query)
            all_params.append(column_group_key)
            all_params += where_params

        full_query = " UNION ALL ".join(queries)

        if offset:
            full_query += ' OFFSET %s '
            all_params.append(offset)
        if limit:
            full_query += ' LIMIT %s '
            all_params.append(limit)

        return (full_query, all_params)

    def _get_aml_line(self, report, parent_line_id, options, eval_dict, init_bal_by_col_group):
        line_columns = []
        for column in options['columns']:
            col_expr_label = column['expression_label']
            col_value = eval_dict[column['column_group_key']].get(col_expr_label)
            col_currency = None

            if col_expr_label == 'amount_currency':
                col_currency = self.env['res.currency'].browse(eval_dict[column['column_group_key']]['currency_id'])
                col_value = None if col_currency == self.env.company.currency_id else col_value
            elif col_expr_label == 'balance':
                col_value += init_bal_by_col_group[column['column_group_key']]

            line_columns.append(report._build_column_dict(
                col_value,
                column,
                options=options,
                currency=col_currency,
            ))

        aml_id = None
        move_name = None
        caret_type = None
        for column_group_dict in eval_dict.values():
            aml_id = column_group_dict.get('id', '')
            if aml_id:
                caret_type = 'account.move.line'
                move_name = column_group_dict['move_name']
                break

        return {
            'id': report._get_generic_line_id('account.move.line', aml_id, parent_line_id=parent_line_id),
            'caret_options': caret_type,
            'parent_id': parent_line_id,
            'name': move_name,
            'columns': line_columns,
            'level': 3,
        }
