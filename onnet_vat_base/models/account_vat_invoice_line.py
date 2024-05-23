# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountVATInvoiceLine(models.Model):
    _name = "account.vat.invoice.line"
    _description = "VAT Invoice Lines"

    invoice_id = fields.Many2one('account.vat.invoice', string="VAT Invoice")
    currency_id = fields.Many2one(related='invoice_id.currency_id',
        depends=['invoice_id.currency_id'], store=True, string="Currency")
    product_id = fields.Many2one("product.product", string="Product")
    # price_unit = fields.Float(string="Giá")
    price_unit = fields.Float(string="Giá", digits='Product Price', compute="_compute_amount")
    quantity = fields.Float(string="Qty")
    name = fields.Char(string="Product's name in VAT-Invoice", required=True)
    invoice_line_tax_ids = fields.Many2one("account.tax", string="Tax")
    # price_total = fields.Integer("Tiền trước thuế", compute="_sub_total")
    # price_subtotal = fields.Integer("Tổng tiền", compute="_sub_total")
    discount = fields.Float("Discount (%)")
    price_total = fields.Monetary(string="Tax include", currency_field='currency_id')
    price_subtotal = fields.Monetary(string="Tax exclude", currency_field='currency_id')

    uom_id = fields.Many2one('uom.uom', string="UoM")
    invoice_uom_id = fields.Char("UoM in VAT-Invoice")
    vat_rate = fields.Integer("VAT Rate", compute="_compute_amount")
    vat_amount = fields.Monetary(
        "VAT Amount", compute="_compute_amount", currency_field='currency_id')
    # is_adjustment_line = fields.Boolean(string="Thuộc hóa đơn điều chỉnh", related='invoice_id.is_adjustment_invoice')
    # is_increase_adj = fields.Boolean(string="Là điều chỉnh tăng", default=False)
    account_move_line_id = fields.Many2one('account.move.line', string="Related internal invoice line")

    @api.depends('quantity', 'invoice_line_tax_ids', 'price_total', 'price_subtotal')
    def _compute_amount(self):
        """
        Compute the amounts of the einvoice line.
        """
        for rec in self:
            if rec.quantity:
                price_unit = rec.price_subtotal / rec.quantity
            else:
                price_unit = 0
            currency = rec.currency_id
            rec.price_unit = price_unit
            rec.vat_rate = int(rec.invoice_line_tax_ids.amount)
            rec.vat_amount = currency.round(rec.price_total - rec.price_subtotal)
