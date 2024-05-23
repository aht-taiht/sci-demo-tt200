from odoo import api, fields, models

class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    brand_id = fields.Char(string='Brand')
    start_date = fields.Date('Start date')
    end_date = fields.Date('End date')
    type = fields.Selection([('service', 'Service'), ('guarantee', 'Guarantee'), ('product', 'Product')],
                            string='Type price list',
                            default='service')