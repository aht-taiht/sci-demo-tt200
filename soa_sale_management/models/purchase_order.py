# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def get_amount_deposit_1st(self):
        if not self.payment_term_id:
            return 0.0
        terms = self.payment_term_id._compute_terms(
            date_ref=self.date_order or fields.Date.context_today(self),
            currency=self.currency_id,
            company=self.company_id,
            tax_amount=self.currency_id._convert(
                self.amount_tax, self.company_id.currency_id, self.company_id, self.date_order),
            tax_amount_currency=self.amount_tax,
            untaxed_amount=self.currency_id._convert(
                self.amount_untaxed, self.company_id.currency_id, self.company_id, self.date_order),
            untaxed_amount_currency=self.amount_untaxed,
            sign=1)
        terms_lines = sorted(terms["line_ids"], key=lambda t: t.get('date'))
        if terms_lines and terms_lines[0]:
            if self.currency_id == self.company_id.currency_id:
                amount = terms_lines[0]['company_amount']
            else:
                amount = terms_lines[0]['foreign_amount']
            return amount
        return 0.0

    def _field_titles(self):
        return {
            'bank': 'Bank: ' if 'source' in self.company_id.name.lower() else 'Beneficiary’s bank: ',
            'account': 'Account Number: ' if 'source' in self.company_id.name.lower() else 'Beneficiary’s account:'
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_data_to_xlsx_report(self):
        pkg_type = self.product_packaging_id.package_type_id

        results = {
            'customer_item_no': self.customer_item_no or '',
            'supplier_item_no': self.supplier_item_no or '',
            'picture': '',
            'description': self.name,
            'material': self.product_id.product_tmpl_id.material or '',
            'colour': self.product_id.product_tmpl_id.color or '',
            'product__W': self.product_id.product_tmpl_id.w_cm or '',
            'product__L': self.product_id.product_tmpl_id.l_cm or '',
            'product__H': self.product_id.product_tmpl_id.h_cm or '',
            'product__hs_code': self.product_id.product_tmpl_id.hs_code or '',
            'product__quantity': self.product_uom_qty,
            'product__unit_price': self.price_unit,
            'product__total_amount': self.price_subtotal,
            'pkg_inner_box__W': pkg_type.width if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__L': pkg_type.packaging_length if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__H': pkg_type.height if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__qty_per_inner_box': self.product_packaging_qty if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__total_inner_box': (self.product_uom_qty / self.product_packaging_qty if self.product_packaging_qty else 0.0)
            if pkg_type.type_packing == 'inner_box' else None,
            'pkg_masterbox__W': pkg_type.width if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__L': pkg_type.packaging_length if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__H': pkg_type.height if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__qty_per_export': self.product_packaging_qty if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__total_export': self.product_packaging_qty if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__nw': pkg_type.nw_packing if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__gw': pkg_type.gw_packing if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__volume_per_export': pkg_type.width * pkg_type.packaging_length * pkg_type.height / 1000000,
            'pkg_masterbox__total_volume': 0.0,
            'pkg_giftbox__W': pkg_type.width if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__L': pkg_type.packaging_length if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__H': pkg_type.height if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__qty_per_pallet': self.product_packaging_qty if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__total_pallet': (self.product_uom_qty / self.product_packaging_qty
                                          if self.product_packaging_qty else 0.0)
            if pkg_type.type_packing == 'pallet' else None,
        }
        results['pkg_masterbox__total_volume'] = results['pkg_masterbox__volume_per_export'] * self.product_packaging_qty
        return results
