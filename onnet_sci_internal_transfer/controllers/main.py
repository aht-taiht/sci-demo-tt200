from odoo.http import request
from ...odoo_restful.controllers.main import APIController

class APIInternalTransfer(APIController):

    def convert_data(self, model, data):
        res = super(APIInternalTransfer, self).convert_data(model, data)
        if model == 'account.move.line':
            for item in res:
                if item.pop('type',False) == 'internal_transfer':
                    journal_id = request.env['account.journal'].search([('internal_transfer', '=', True)],limit=1)
                    if journal_id:
                        item['journal_id'] = journal_id.id
                    if item.get('product_code', False):
                        product = request.env['product.product'].search([('default_code', '=', item.pop('product_code'))], limit=1)
                        if product:
                            if item.get('debit', False):
                                item['account_id'] = product.categ_id.property_stock_account_input_categ_id.id
                            elif item.get('credit', False):
                                item['account_id'] = product.categ_id.property_stock_account_output_categ_id.id
        elif model == 'account.move':
            for item in res:
                if item.pop('type',False) == 'internal_transfer':
                    journal_id = request.env['account.journal'].search([('internal_transfer', '=', True)], limit=1)
                    if journal_id:
                        item['journal_id'] = journal_id.id
        return res