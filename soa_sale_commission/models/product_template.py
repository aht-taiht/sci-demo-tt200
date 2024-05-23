# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    commission_fee = fields.Boolean(string='Commission Fee', default=False, copy=False)
