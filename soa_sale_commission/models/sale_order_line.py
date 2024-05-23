# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    commission_percent = fields.Float(string='Comm.%(commission)', default=0.0)
    commission_move_ids = fields.One2many('stock.move', 'sale_line_commission_id', string='Commission Moves')

    @api.depends('commission_percent')
    def _compute_amount(self):
        return super(SaleOrderLine, self)._compute_amount()

    def _convert_to_tax_base_line_dict(self, **kwargs):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        if self.commission_percent:
            return self.env['account.tax']._convert_to_tax_base_line_dict(
                self,
                partner=self.order_id.partner_id,
                currency=self.order_id.currency_id,
                product=self.product_id,
                taxes=self.tax_id,
                price_unit=self._get_price_unit_commission(),
                quantity=self.product_uom_qty,
                discount=self.discount,
                price_subtotal=self.price_subtotal,
                **kwargs,
            )
        return super()._convert_to_tax_base_line_dict()

    def _get_price_unit_commission(self):
        self.ensure_one()
        return (self.price_unit * self.commission_percent) / 100

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.order_id.is_sale_commission and self.commission_percent:
            res.update({'price_unit': (self.price_unit * self.commission_percent) / 100})
        return res
