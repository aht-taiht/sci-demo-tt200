# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime

from markupsafe import Markup

from odoo import models, api, fields, _, Command, tools
from odoo.exceptions import ValidationError, UserError
from odoo.tools import get_lang
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF

PAYMENT_STATE_SELECTION = [
    ('not_paid', 'Not Paid'),
    ('paid', 'Paid'),
    ('partial', 'Partially Paid'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cashflow_forecast_ids = fields.One2many('account.cashflow.forecast', 'sale_order_id',
                                            string='Account Cashflow Forecast')
    account_payment_ids = fields.Many2many(
        'account.payment', compute='_get_payment', string='Payments', store=False)
    payment_count = fields.Integer(string="Payment Count", compute='_get_payment')
    payment_state = fields.Selection(
        selection=PAYMENT_STATE_SELECTION,
        string="Payment Status",
        compute='_compute_payment_state', store=True, readonly=True,
        copy=False,
        tracking=True,
    )

    @api.constrains('cashflow_forecast_ids')
    def _check_amount_planned_over_total_amount(self):
        if not self.cashflow_forecast_ids:
            return
        groupby_vals = tools.groupby(self.cashflow_forecast_ids, lambda cf_line: (cf_line.sale_order_id, cf_line.purchase_order_id))
        for groupby_key, cf_lines in groupby_vals:
            sale_id, purchase_order_id = groupby_key
            amount_currency_planned = sum([line.amount_currency for line in cf_lines])
            purchase_allowed_diff = 10 ** (-purchase_order_id.currency_id.decimal_places) * 2
            sale_allowed_diff = 10 ** (-sale_id.currency_id.decimal_places) * 2
            if sale_id and purchase_order_id:
                check_diff = abs(amount_currency_planned) - purchase_order_id.amount_total
                if check_diff > purchase_allowed_diff:
                    raise UserError(_('The amount exceeds the value of the total of the Purchase Order: %s', purchase_order_id.name))
            if sale_id and not purchase_order_id:
                if (amount_currency_planned - sale_id.amount_total) > sale_allowed_diff:
                    raise UserError(_('The amount exceeds the value of the total of the Sale Order: %s', sale_id.name))

    def _get_payment(self):
        for order in self:
            payments = self.env['account.payment'].search([
                '|', ('sale_order_ids', '=', order.id), ('sale_order_id', '=', order.id)])
            order.account_payment_ids = payments
            order.payment_count = len(order.account_payment_ids)

    @api.depends(
        'amount_total',
        'order_line.invoice_lines.move_id',
        'order_line.invoice_lines.move_id.state',
        'order_line.invoice_lines.move_id.payment_state',
        'order_line.invoice_lines.move_id.amount_total',
    )
    def _compute_payment_state(self):
        for order in self:
            order.payment_state = 'not_paid'
            invoice_ids = order.order_line.invoice_lines.move_id.filtered(lambda m: m.state == 'posted')
            if invoice_ids:
                if (all(inv.payment_state == 'paid' for inv in invoice_ids)
                        and sum(inv.amount_total for inv in invoice_ids) >= order.amount_total):
                    order.payment_state = 'paid'
                elif any(inv.payment_state in ('partial', 'paid') for inv in invoice_ids):
                    order.payment_state = 'partial'
                else:
                    order.payment_state = 'not_paid'

    def write(self, vals):
        edited_lines = defaultdict(lambda: {'schedule_date': tuple(), 'amount_currency': tuple()})
        if vals.get('cashflow_forecast_ids'):
            for line_val in vals.get('cashflow_forecast_ids'):
                if line_val[0] == Command.UPDATE:
                    line_id = self.env['account.cashflow.forecast'].browse(line_val[1])
                    if 'schedule_date' in line_val[2]:
                        edited_lines[line_id]['schedule_date'] = (line_id.schedule_date, datetime.strptime(line_val[2]['schedule_date'], DF))
                    if 'amount_currency' in line_val[2] and line_id.amount_currency != line_val[2]['amount_currency']:
                        edited_lines[line_id]['amount_currency'] = (line_id.amount_currency, line_val[2]['amount_currency'])
        res = super(SaleOrder, self).write(vals)
        if edited_lines:
            msg = Markup(_("<b style='color: orange'>Updated Cashflow Line:</b><br/>"))
            date_format = get_lang(self.env).date_format
            edited_list_msg = []
            for line, vals in edited_lines.items():
                line_msg = f"- <b>{line.payment_term_id.name} ({line.ref}) has changed:</b> <br/> <ul>"
                if vals['schedule_date']:
                    line_msg += f"<li>{_('Schedule date:')} {vals['schedule_date'][0].strftime(date_format)} -> {vals['schedule_date'][1].strftime(date_format)}</li>"
                if vals['amount_currency']:
                    line_msg += f"<li>{_('Planned Amount in Currency:')} {line.currency_id.format(vals['amount_currency'][0])} -> {line.currency_id.format(vals['amount_currency'][1])}</li>"
                line_msg += "</ul>"
                edited_list_msg.append(Markup(line_msg))
            body = msg + Markup('').join([*edited_list_msg])
            self.message_post(body=body)
        return res

    def action_create_cashflow_forecast(self):
        self.cashflow_forecast_ids = False
        cf_forecast = []
        cf_sales = self._prepare_cashflow_sale_order()
        cf_forecast.extend(cf_sales)
        if self.order_line.mapped('purchase_line_ids'):
            purchase_ids = self.order_line.mapped('purchase_line_ids.order_id')
            for purchase_id in purchase_ids:
                cf_purchase = self._prepare_cashflow_purchase_order(purchase_id)
                cf_forecast.extend(cf_purchase)
        self.cashflow_forecast_ids = cf_forecast

    def _prepare_cashflow_sale_order(self):
        cf_sale_forecast = []
        payment_term_id = self.payment_term_id
        total_amount = self.amount_total
        residual_amount = total_amount
        line_ids = payment_term_id.line_ids
        for i, line in enumerate(line_ids):
            vals = {
                'ref': self.name,
                'payment_term_id': payment_term_id.id,
                'delay_type': line.delay_type,
                'nb_days': line.nb_days,
                'description': str(line.nb_days) + " day(s) " + dict(line._fields['delay_type'].selection).get(
                    line.delay_type),
            }
            # get schedule date
            if line.delay_type == 'days_after_etd':
                vals['schedule_date'] = line._get_due_date(self.etd_order)
            elif line.delay_type == 'days_after_order':
                vals['schedule_date'] = line._get_due_date(self.date_order)
            else:
                vals['schedule_date'] = line._get_due_date(self.atd_order)

            # get amount
            if i == len(line_ids) - 1:
                vals['amount_currency'] = residual_amount
            elif line.value == 'fixed':
                vals['amount_currency'] = line.value_amount
            else:
                vals['amount_currency'] = total_amount * (line.value_amount / 100.0)
            residual_amount -= vals['amount_currency']
            cf_sale_forecast.append((0, 0, vals))
        return cf_sale_forecast

    def _prepare_cashflow_purchase_order(self, purchase_id):
        cf_purchase_forecast = []
        payment_term_id = purchase_id.payment_term_id
        total_amount = purchase_id.amount_total
        residual_amount = total_amount
        line_ids = payment_term_id.line_ids
        for i, line in enumerate(line_ids):
            vals = {
                'ref': purchase_id.name,
                'purchase_order_id': purchase_id.id,
                'payment_term_id': payment_term_id.id,
                'delay_type': line.delay_type,
                'nb_days': line.nb_days,
                'description': str(line.nb_days) + " day(s) " + dict(line._fields['delay_type'].selection).get(
                    line.delay_type),
            }

            # get schedule date
            if line.delay_type == 'days_after_etd':
                vals['schedule_date'] = line._get_due_date(self.etd_order)
            elif line.delay_type == 'days_after_order':
                vals['schedule_date'] = line._get_due_date(purchase_id.date_approve)
            else:
                vals['schedule_date'] = line._get_due_date(self.atd_order)

            # get amount
            if i == len(line_ids) - 1:
                vals['amount_currency'] = -residual_amount
            elif line.value == 'fixed':
                vals['amount_currency'] = -line.value_amount
            else:
                vals['amount_currency'] = -total_amount * (line.value_amount / 100.0)
            residual_amount += vals['amount_currency']
            cf_purchase_forecast.append((0, 0, vals))
        return cf_purchase_forecast

    def create_payment(self):
        amount = self.amount_total
        payment_amount = 0
        if self.account_payment_ids:
            payment_amount += sum(x.amount for x in self.account_payment_ids)
        residual_amount = amount - payment_amount

        analytic_value = False
        if self.analytic_account_id:
            analytic_value = {self.analytic_account_id.id: 100}

        if residual_amount > 0:
            return {
                'name': _('Create Deposit'),
                'res_model': 'account.payment.wizard',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'context': {
                    'active_model': 'sale.order',
                    'active_id': self.id,
                    'default_partner_id': self.partner_id.id,
                    'default_amount': residual_amount,
                    'default_analytic_distribution': analytic_value
                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
        else:
            raise ValidationError(_("The full payment for this sales order has been made."))

    def action_view_payment(self, payments=False):
        if not payments:
            payments = self.mapped('account_payment_ids')
        action = self.env['ir.actions.actions']._for_xml_id('account.action_account_payments')
        if len(payments) > 1:
            action['domain'] = [('id', 'in', payments.ids)]
        elif len(payments) == 1:
            form_view = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = payments.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action
