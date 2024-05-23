# -*- coding: utf-8 -*-

from odoo import models, api, fields, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    sale_order_id = fields.Many2one(
        'sale.order', string='Sale Order', readonly=False, store=True, tracking=True)
    sale_order_ids = fields.Many2many(
        'sale.order', 'account_payment_sale_order_rel', 'payment_id', 'sale_id',
        string='Sale Order', compute='_compute_related_order', readonly=False, store=True)
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Purchase Order', readonly=False, store=True, tracking=True)
    purchase_order_ids = fields.Many2many(
        'purchase.order', 'account_payment_purchase_order_rel', 'payment_id', 'purchase_id',
        string='Purchase Order', compute='_compute_related_order', readonly=False, store=True)
    analytic_distribution = fields.Json(
        'Analytic Distribution', store=True, copy=True, readonly=False)

    @api.depends('is_reconciled', 'reconciled_invoice_ids', 'reconciled_bill_ids', 'sale_order_id', 'purchase_order_id')
    def _compute_related_order(self):
        for payment in self:
            if payment.partner_type == 'customer' and payment.reconciled_invoice_ids:
                sale_order_ids = payment.reconciled_invoice_ids.line_ids.sale_line_ids.order_id
                if sale_order_ids:
                    payment.sale_order_ids |= sale_order_ids
            elif payment.partner_type == 'supplier' and payment.reconciled_bill_ids:
                purchase_order_ids = payment.reconciled_bill_ids.line_ids.purchase_order_id
                if purchase_order_ids:
                    payment.purchase_order_ids |= purchase_order_ids
            if payment.sale_order_id:
                payment.sale_order_ids |= payment.sale_order_id
            if payment.purchase_order_id:
                payment.purchase_order_ids |= payment.purchase_order_id

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        value_lst = super()._prepare_move_line_default_vals(write_off_line_vals, force_balance)
        if self.analytic_distribution:
            for item in value_lst:
                item['analytic_distribution'] = self.analytic_distribution
        return value_lst
