# -*- coding: utf-8 -*-

from odoo import models, api, fields, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    packing_type = fields.Text(string='Packing Type')
    dimension = fields.Text(string='Dimension')
    supplier_code = fields.Char(string='Supplier Code')
    customer_code = fields.Char(string='Customer Code')
    factory_code = fields.Char(string='Factory Code')
    factory_barcode = fields.Char(string='Factory Barcode')
    const_quantity = fields.Integer(string='Const Quantity')
    material = fields.Char(string='Material')
    color = fields.Char(string='Color')
    w_cm = fields.Float(string='W (cm)')
    l_cm = fields.Float(string='L (cm)')
    h_cm = fields.Float(string='H (cm)')
    hs_code = fields.Char(string='HS Code')
    shelf_life = fields.Char(string='Shelf Life')
