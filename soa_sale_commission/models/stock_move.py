# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class StockMove(models.Model):
    _inherit = 'stock.move'

    sale_line_commission_id = fields.Many2one('sale.order.line', string='Sale Line Commission')