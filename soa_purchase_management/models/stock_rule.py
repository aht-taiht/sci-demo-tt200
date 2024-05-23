# -*- encoding: utf-8 -*-

from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _prepare_purchase_order(self, company_id, origins, values):
        res = super(StockRule, self)._prepare_purchase_order(company_id, origins, values)
        values = values[0]
        sale_order_id = values['group_id'].sale_id
        if sale_order_id and sale_order_id.analytic_account_id:
            res['analytic_account_id'] = sale_order_id.analytic_account_id.id
        return res
