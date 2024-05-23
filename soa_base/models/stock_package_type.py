# -*- coding: utf-8 -*-

from odoo import models, api, fields, _


class StockPackageType(models.Model):
    _inherit = 'stock.package.type'

    type_packing = fields.Selection([
        ('master_box', 'Master Box'),
        ('inner_box', 'Inner Box'),
        # ('gift_box', 'Gift Box'),
        ('pallet', 'Pallet'),
    ], string='Packing Type')
    nw_packing = fields.Float(string='NW (kg)')
    gw_packing = fields.Float(string='GW (kg)')
