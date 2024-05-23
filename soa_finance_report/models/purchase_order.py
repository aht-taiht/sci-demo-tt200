# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

PAYMENT_STATE_SELECTION = [
    ('not_paid', 'Not Paid'),
    ('paid', 'Paid'),
    ('partial', 'Partially Paid'),
]


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_account_move_line(self, move=False):
        res = super(PurchaseOrderLine, self)._prepare_account_move_line(move)
        analytic_account_id = self.order_id.analytic_account_id.id
        if analytic_account_id and not self.display_type:
            analytic_account_id = str(analytic_account_id)
            if 'analytic_distribution' in res:
                res['analytic_distribution'][analytic_account_id] = res['analytic_distribution'].get(analytic_account_id, 0) + 100
            else:
                res['analytic_distribution'] = {analytic_account_id: 100}
        return res


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # account_payment_ids = fields.One2many('account.payment', 'purchase_order_id', string='Account Payment')
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

    @api.depends('account_payment_ids')
    def _get_payment(self):
        for order in self:
            payments = self.env['account.payment'].search([
                '|', ('purchase_order_ids', '=', order.id), ('purchase_order_id', '=', order.id)])
            order.account_payment_ids = payments
            order.payment_count = len(order.account_payment_ids)

    @api.depends(
        'amount_total',
        'order_line.invoice_lines.move_id',
        'order_line.invoice_lines.move_id.state',
        'order_line.invoice_lines.move_id.payment_state',
        'order_line.invoice_lines.move_id.amount_total',)
    def _compute_payment_state(self):
        for item in self:
            item.payment_state = 'not_paid'
            invoice_ids = item.order_line.invoice_lines.move_id.filtered(lambda m: m.state == 'posted')
            if invoice_ids:
                if (all(inv.payment_state == 'paid' for inv in invoice_ids)
                        and sum(inv.amount_total for inv in invoice_ids) >= item.amount_total):
                    item.payment_state = 'paid'
                elif any(inv.payment_state in ('partial', 'paid') for inv in invoice_ids):
                    item.payment_state = 'partial'
                else:
                    item.payment_state = 'not_paid'

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
                'name': _('Create Advance'),
                'res_model': 'account.payment.wizard',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'context': {
                    'active_model': 'purchase.order',
                    'active_id': self.id,
                    'default_partner_id': self.partner_id.id,
                    'default_amount': residual_amount,
                    'default_analytic_distribution': analytic_value
                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
        else:
            raise ValidationError(_("The full payment for this purchase order has been made."))

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
