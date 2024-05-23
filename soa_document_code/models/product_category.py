# -*- coding: utf-8 -*-
from odoo import api, models, fields, _


class ProductCategory(models.Model):
    _inherit = 'product.category'

    category_code = fields.Char('Category Code')
    product_sequence_id = fields.Many2one('ir.sequence', copy=False)

    _sql_constraints = [('code_unique', 'unique(category_code)', 'Other product category already used this code .')]

    def action_update_sequence(self):
        for record in self:
            if not record.product_sequence_id:
                categ_name = record.name.split(' ')
                name = [c_name.lower() for c_name in categ_name]
                values = {
                    'name': 'Category ' + record.name,
                    'implementation': 'no_gap',
                    'code': '.'.join(name),
                    'prefix': record.category_code,
                    'padding': 5,
                }
                sequence_id = self.env['ir.sequence'].sudo().create(values)
                record.product_sequence_id = sequence_id.id
            else:
                record.product_sequence_id.sudo().update({
                    'prefix': record.category_code,
                    'padding': 5,
                })

    @api.model_create_multi
    def create(self, vals_list):
        categories = super(ProductCategory, self).create(vals_list)
        for category in categories:
            if category.category_code:
                category.action_update_sequence()
        return categories

    def write(self, vals):
        res = super(ProductCategory, self).write(vals)
        if 'category_code' in vals:
            self.action_update_sequence()
        # TODO: update code for all product
        return res


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_update_seq(self, categ_id):
        sequence = False
        if categ_id.product_sequence_id:
            sequence = categ_id.product_sequence_id.sudo().next_by_code(categ_id.product_sequence_id.code)
        self.default_code = sequence

    @api.model_create_multi
    def create(self, vals_list):
        products = super(ProductTemplate, self).create(vals_list)
        for product in products:
            categ_id = product.categ_id
            if categ_id:
                while categ_id and not categ_id.category_code:
                    categ_id = categ_id.parent_id

                if not categ_id.product_sequence_id:
                    categ_id.action_update_sequence()
                product.action_update_seq(categ_id)
        return products

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        if 'categ_id' in vals:
            for product in self:
                categ_id = product.categ_id
                if categ_id:
                    while categ_id and not categ_id.category_code:
                        categ_id = categ_id.parent_id

                    if not categ_id.product_sequence_id:
                        categ_id.action_update_sequence()
                    product.action_update_seq(categ_id)
        return res


# class ProductProduct(models.Model):
#     _inherit = 'product.product'

#     def action_update_seq(self):
#         sequence = self.categ_id.product_sequence_id.sudo().next_by_code(self.categ_id.product_sequence_id.code)
#         self.default_code = sequence

#     @api.model_create_multi
#     def create(self, vals_list):
#         products = super(ProductProduct, self).create(vals_list)
#         for product in products:
#             if product.categ_id and product.categ_id.category_code:
#                 if not product.categ_id.product_sequence_id:
#                     product.categ_id.action_update_sequence()
#                 product.action_update_seq()
#         return products

#     def write(self, vals):
#         res = super(ProductProduct, self).write(vals)
#         if 'categ_id' in vals:
#             for product in self:
#                 if product.categ_id and product.categ_id.category_code:
#                     if not product.categ_id.product_sequence_id:
#                         product.categ_id.action_update_sequence()
#                     product.action_update_seq()
#         return res
