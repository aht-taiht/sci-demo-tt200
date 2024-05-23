# -*- coding: utf-8 -*-

from datetime import timedelta
import itertools

from markupsafe import Markup

from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError, UserError
from odoo.tools import get_lang


# ---------------------------------------------------------
# Budgets
# ---------------------------------------------------------
class AccountBudgetPost(models.Model):
    _inherit = "account.budget.post"

    company_id = fields.Many2one(required=False)


class AccountExpenseAllocation(models.Model):
    _name = 'account.expense.allocation'
    _description = 'Account PNL Allocation'
    _order = 'date_from, to_analytic_plan_id'

    budget_id = fields.Many2one('crossovered.budget', 'Budget', ondelete='cascade')
    from_analytic_plan_ids = fields.Many2many(
        'account.analytic.plan', 'acc_expense_alloc_from_plan', string='Source BU')
    to_analytic_plan_id = fields.Many2one(
        'account.analytic.plan', string='Destination BU')
    date_from = fields.Date('From Date')
    date_to = fields.Date('To Date ')
    rate = fields.Float('Rate (%)')

    @api.constrains('rate')
    def _check_rate(self):
        if not all(0.0 <= allocation.rate <= 100 for allocation in self):
            raise UserError(_("The rate of the Period must be between 0 and 100."))

    @api.constrains('date_from', 'date_to')
    def _check_date_from_date_to(self):
        if any(allocation.date_to and allocation.date_from > allocation.date_to for allocation in self):
            raise UserError(_("The Start Date of the Period must be less than End Date."))
        if any((allocation.date_from < allocation.budget_id.date_from or allocation.date_to > allocation.budget_id.date_to)
               and allocation.budget_id.date_from and allocation.budget_id.date_to
               for allocation in self):
            raise UserError(_("The a date interval date must be in range of the budget period !"))

    @api.constrains('date_from', 'date_to', 'to_analytic_plan_id', 'budget_id')
    def _check_compare_overlap_dates(self):
        if not self:
            return
        all_existing_allocations = self.env['account.expense.allocation'].search([
            ('date_from', '<=', max(self.mapped('date_to'))),
            ('date_to', '>=', min(self.mapped('date_from'))),
            ('budget_id.state', 'not in', ('draft', 'cancel'))
        ])
        for record in self:
            existing_allocations = all_existing_allocations.filtered(lambda allocation:
                    record.id != allocation.id
                    and record['date_from'] <= allocation['date_to']
                    and record['date_to'] >= allocation['date_from'])
            if record.to_analytic_plan_id:
                existing_allocations = existing_allocations.filtered(lambda l: l.to_analytic_plan_id == record.to_analytic_plan_id)
            if existing_allocations:
                raise ValidationError(_('Two allocation can not be overlapped time each other for the same analytic plan.'))


class CrossoveredBudget(models.Model):
    _inherit = 'crossovered.budget'

    company_id = fields.Many2one(required=False, default=False)
    currency_id = fields.Many2one(
        'res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    expense_allocation_ids = fields.One2many(
        'account.expense.allocation', 'budget_id', string='Allocation Lines')

    @api.constrains('state')
    def _check_compare_overlap_dates(self):
        self.expense_allocation_ids._check_compare_overlap_dates()

    def write(self, vals):
        edited_lines = {}
        deleted_lines = []
        if vals.get('crossovered_budget_line') and self.state != 'draft':
            for line_val in vals.get('crossovered_budget_line'):
                if line_val[0] == Command.UPDATE:
                    line_id = self.env['crossovered.budget.lines'].browse(line_val[1])
                    if 'reforecast_amount' in line_val[2] and line_id.reforecast_amount != line_val[2]['reforecast_amount']:
                        edited_lines.update({line_id: [line_id.reforecast_amount, line_val[2]['reforecast_amount']]})
                elif line_val[0] in [Command.UNLINK, Command.DELETE]:
                    line_id = self.env['crossovered.budget.lines'].browse(line_val[1])
                    deleted_lines.append(f"- {line_id.display_name} {_('in')} "
                                         f"{line_id.date_to.strftime(get_lang(self.env).date_format)} is deleted")
        res = super(CrossoveredBudget, self).write(vals)
        if edited_lines or deleted_lines:
            msg = Markup(_("<b>Updated reforecast amount in the confirmed state:</b><br/>"))
            edited_list_msg = [
                (f"- {line.display_name} {_('in')} {line.date_to.strftime(get_lang(self.env).date_format)} :"
                 f" {line.currency_id.format(val[0])} "
                 f" -> {line.currency_id.format(val[1])}")
                for line, val in edited_lines.items()]
            body = msg + Markup('<br/>').join([*edited_list_msg, *deleted_lines])
            self.message_post(body=body)
        return res


class CrossoveredBudgetLines(models.Model):
    _inherit = "crossovered.budget.lines"

    currency_id = fields.Many2one(
        'res.currency', related='crossovered_budget_id.currency_id', readonly=True, store=True)
    analytic_plan_id = fields.Many2one(
        'account.analytic.plan',  string='Business Unit', related=None, readonly=False, store=True)
    reforecast_amount = fields.Monetary(
        'Reforecast Amount', required=True, help="Amount you forecast to earn/spend.")

    @api.constrains('general_budget_id', 'analytic_plan_id')
    def _must_have_analytical_or_budgetary_or_both(self):
        for record in self:
            if not record.analytic_account_id and not record.general_budget_id:
                raise ValidationError(
                    _("You have to enter at least a budgetary position or analytic account on a budget line."))

    def _get_query_currency_table(self, company_ids, currency_id, conversion_date):
        """
        Prepare values of currency table for all companies
            return str -> Ex: (VALUES (1, 1, 0)) AS currency_table(company_id, rate, precision)
        """
        companies = self.env['res.company'].search([])  # TODO: remove the argument 'company_ids'
        user_company = self.env.company
        currency_model = self.env['res.currency']
        currency_rates = currency_model.search([('active', '=', True)])._get_rates(user_company, conversion_date)
        conversion_rates = []
        for company in companies:
            conversion_rates.extend((
                company.id,
                currency_rates[currency_id.id] / currency_rates[company.currency_id.id],
                currency_id.decimal_places,
            ))
        query = '(VALUES %s) AS currency_table(company_id, rate, precision)' % ','.join('(%s, %s, %s)' for i in companies)
        return self.env.cr.mogrify(query, conversion_rates).decode(self.env.cr.connection.encoding)

    # Override method base: _compute_practical_amount
    def _compute_practical_amount(self):
        # Set all companies to context 'allowed_companies_ids', for get records in the multi companies
        allowed_company_ids = self.env['res.company'].search([]).ids
        self.with_context(allowed_company_ids=allowed_company_ids)
        for line in self:
            acc_ids = line.general_budget_id.sudo().account_ids.ids
            date_to = line.date_to
            date_from = line.date_from
            currency_id = line.currency_id

            currency_table_query = self._get_query_currency_table(
                self.env.company.ids, currency_id=currency_id, conversion_date=line.date_to.strftime('%Y-%m-%d'))

            if line.analytic_plan_id.id:
                analytic_line_obj = self.env['account.analytic.line'].with_context(allowed_company_ids=allowed_company_ids)
                analytic_account_ids = self.env['account.analytic.account'].sudo().search([
                    ('plan_id', "child_of", line.analytic_plan_id.id)
                ])
                domain = [
                    (f'{line.analytic_plan_id._column_name()}', 'in', analytic_account_ids.ids),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to)
                ]
                if acc_ids:
                    domain += [('general_account_id', 'in', acc_ids)]

                where_query = analytic_line_obj._where_calc(domain)
                analytic_line_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = f"""
                SELECT COALESCE(SUM(ROUND(account_analytic_line.amount * currency_table.rate, currency_table.precision)), 0.0) AS sum
                FROM {from_clause}
                JOIN {currency_table_query} ON currency_table.company_id = account_analytic_line.company_id
                WHERE {where_clause}
                """
                self.env.cr.execute(select, where_clause_params)
                result = self.env.cr.fetchone()
                line.practical_amount = result[0] or 0.0
            else:
                line.practical_amount = 0.0

    # Override method base: action_open_budget_entries
    def action_open_budget_entries(self):
        if self.analytic_plan_id:
            analytic_account_ids = self.env['account.analytic.account'].search([
                ('plan_id', "child_of", self.analytic_plan_id.id)
            ])
            # SOA Custom: Domain to search account.analytic.line
            domain = [
                (f'{self.analytic_plan_id._column_name()}', 'in', analytic_account_ids.ids),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ]
            if self.general_budget_id:
                domain += [('general_account_id', 'in', self.general_budget_id.account_ids.ids)]

            analytic_lines = self.env['account.analytic.line'].search(domain)
            action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all_a')
            action['domain'] = [('id', 'in', analytic_lines.mapped('move_line_id.id'))]
        else:
            # otherwise the journal entries booked on the accounts of the budgetary postition are opened
            action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all_a')
            action['domain'] = [('account_id', 'in', self.general_budget_id.account_ids.ids),
                                ('date', '>=', self.date_from),
                                ('date', '<=', self.date_to)
                                ]
        return action
