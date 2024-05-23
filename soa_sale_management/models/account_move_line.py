
from odoo import fields, models, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    price_unit_inl_tax = fields.Float(string='Unit Price Incl Tax', compute='_compute_price_unit_inl_tax')

    def _compute_price_unit_inl_tax(self):
        for line in self:
            line.price_unit_inl_tax = line._prepare_edi_vals_to_export()['price_total_unit']

    def _prepare_data_to_xlsx_report(self):

        order_line = self.sale_line_ids and self.sale_line_ids[-1] or self.sale_line_ids
        pkg_type = order_line.product_packaging_id.package_type_id

        results = {
            'customer_item_no': order_line.customer_item_no or '',
            'supplier_item_no': order_line.supplier_item_no or '',
            'picture': '',
            'description': self.name,
            'material': order_line.product_id.product_tmpl_id.material or '',
            'colour': order_line.product_id.product_tmpl_id.color or '',
            'product__W': order_line.product_id.product_tmpl_id.w_cm or '',
            'product__L': order_line.product_id.product_tmpl_id.l_cm or '',
            'product__H': order_line.product_id.product_tmpl_id.h_cm or '',
            'product__hs_code': order_line.product_id.product_tmpl_id.hs_code or '',
            'product__quantity': self.quantity,
            'product__unit_price': self.price_unit,
            'product__total_amount': self.price_subtotal,
            'pkg_inner_box__W': pkg_type.width if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__L': pkg_type.packaging_length if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__H': pkg_type.height if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__qty_per_inner_box': order_line.product_packaging_qty if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__total_inner_box': (
                self.quantity / order_line.product_packaging_qty if order_line.product_packaging_qty else 0.0)
            if pkg_type.type_packing == 'inner_box' else None,
            'pkg_masterbox__W': pkg_type.width if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__L': pkg_type.packaging_length if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__H': pkg_type.height if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__qty_per_export': order_line.product_packaging_qty if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__total_export': order_line.product_packaging_qty if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__nw': pkg_type.nw_packing if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__gw': pkg_type.gw_packing if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__volume_per_export': pkg_type.width * pkg_type.packaging_length * pkg_type.height / 1000000,
            'pkg_masterbox__total_volume': 0.0,
            'pkg_giftbox__W': pkg_type.width if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__L': pkg_type.packaging_length if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__H': pkg_type.height if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__qty_per_pallet': order_line.product_packaging_qty if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__total_pallet': (self.quantity / order_line.product_packaging_qty
                                          if order_line.product_packaging_qty else 0.0)
            if pkg_type.type_packing == 'pallet' else None,
        }
        results['pkg_masterbox__total_volume'] = results['pkg_masterbox__volume_per_export'] * order_line.product_packaging_qty
        return results