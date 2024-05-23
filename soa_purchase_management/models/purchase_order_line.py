# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    customer_item_no = fields.Char(string='Customer Item No', related='product_id.customer_code')
    supplier_item_no = fields.Char(string='Supplier Item No', related='product_id.supplier_code')
    image_po = fields.Image(string='Picture', related='product_id.image_1920')
    material_po = fields.Char(string='Material', related='product_id.material')

    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id')

    # Sourcing info
    package_type_id = fields.Many2one(related='product_packaging_id.package_type_id')
    material = fields.Char(related='product_tmpl_id.material')
    color = fields.Char(related='product_tmpl_id.color')
    w_cm = fields.Float(related='product_tmpl_id.w_cm')
    h_cm = fields.Float(related='product_tmpl_id.h_cm')
    l_cm = fields.Float(related='product_tmpl_id.l_cm')
    hs_code = fields.Char(related='product_tmpl_id.hs_code')

    package_w_cm = fields.Float(related='package_type_id.width', string="W (cm) Package")
    package_h_cm = fields.Float(related='package_type_id.height', string="H (cm) Package")
    package_l_cm = fields.Float(related='package_type_id.packaging_length', string="L (cm) Package")
    nw_packing = fields.Float(related='package_type_id.nw_packing', string="NW (kg)")
    gw_packing = fields.Float(related='package_type_id.gw_packing', string="GM (kg)")
    volume_export = fields.Float(compute='_compute_volume', string="Volume Per Export (cbm)")
    total_volume = fields.Float(compute='_compute_volume', string="Total Volume (cbm)")

    @api.depends('package_h_cm', 'package_w_cm', 'package_l_cm')
    def _compute_volume(self):
        for line in self:
            volume_export = line.package_w_cm * line.package_h_cm * line.package_l_cm / 1_000_000
            line.volume_export = volume_export
            line.total_volume = volume_export * line.product_packaging_qty
