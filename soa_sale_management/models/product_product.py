# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # override
    def get_product_multiline_description_sale(self):
        """ Compute a multiline description of this product, in the context of sales
                (do not use for purchases or other display reasons that don't intend to use "description_sale").
            It will often be used as the default description of a sale order line referencing this product.
        """
        name = self.name
        if self.description_sale:
            name += '\n' + self.description_sale

        return name


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _get_length_uom_id_from_ir_config_parameter(self):
        product_length_in_feet_param = self.env['ir.config_parameter'].sudo().get_param('product.volume_in_cubic_feet')
        if product_length_in_feet_param == '1':
            return self.env.ref('uom.product_uom_foot')
        else:
            return self.env.ref('uom.product_uom_cm')
