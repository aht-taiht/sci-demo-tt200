# -*- coding: utf-8 -*-

from odoo import models, api, fields

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        payments = super()._create_payments()
        # check assign sale order
        sale_orders = self.line_ids.mapped('move_id.line_ids.sale_line_ids.order_id')
        if sale_orders:
            for so_payment in payments:
                for sale_order in sale_orders:
                    so_payment.sale_order_id = sale_order.id

        # check assign purchase order
        purchase_orders = self.line_ids.mapped('move_id.line_ids.purchase_order_id')
        if purchase_orders:
            for po_payment in payments:
                for purchase_order in purchase_orders:
                    po_payment.purchase_order_id = purchase_order.id
        return payments