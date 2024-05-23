from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = "product.template"

    alternative_product_ids = fields.Many2many('product.template', 'product_alternative_rel', 'src_id', 'dest_id',
                                               string='Alternative Products', help='Suggest alternatives to your customer'
                                               '(upsell strategy).Those product show up on the product page.')
    is_medicine = fields.Boolean(string='Medicine', help='Check if the product is a medicine')
    is_bed = fields.Boolean(string='Bed', help='Check if the product is a bed')
    is_vaccine = fields.Boolean(string='Vaccine', help='Check if the product is a vaccine')
    is_medical_supply = fields.Boolean(string='Medical Supply', help='Check if the product is a medical supply')
    is_insurance_plan = fields.Boolean(string='Insurance Plan', help='Check if the product is an insurance plan')