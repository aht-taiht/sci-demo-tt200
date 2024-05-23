from odoo import api, fields, models

class ProductProduct(models.Model):
    _inherit = "product.product"

    type_product_crm = fields.Selection([('course', 'Course'), ('service_crm', 'Service'), ('product', 'Product')],
                                        string='Type Product crm')
    hide_in_report = fields.Boolean(string='Ẩn trong báo cáo', default=False)