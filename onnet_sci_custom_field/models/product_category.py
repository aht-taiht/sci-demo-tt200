from odoo import api, fields, models

class ProductCategory(models.Model):
    _inherit = "product.category"

    code = fields.Char("Mã")