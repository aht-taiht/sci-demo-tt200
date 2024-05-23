# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_sale_commission = fields.Boolean(string='Is Sale Commission', default=False)
    sale_commission_ids = fields.Many2many(
        'sale.order', 'sale_order_commission_rel', 'order_id', 'commission_id', string='Sale Commission', copy=False)
    sale_commission_count = fields.Integer(string='Sale Commission Count', compute='_compute_commission_count')
    sale_ids = fields.Many2many(
        'sale.order', 'sale_order_commission_rel', 'commission_id', 'order_id', string='Sale Orders', copy=False)
    sale_count = fields.Integer(string='Sale Count', compute='_compute_sale_count')

    @api.depends('sale_commission_ids')
    def _compute_commission_count(self):
        for item in self:
            item.sale_commission_count = len(item.sale_commission_ids)

    @api.depends('sale_ids')
    def _compute_sale_count(self):
        for item in self:
            item.sale_count = len(item.sale_ids)

    def action_view_sale_commission(self, commissions=False):
        if not commissions:
            commissions = self.mapped('sale_commission_ids')
        action = self.env['ir.actions.actions']._for_xml_id('sale.action_quotations_with_onboarding')
        if len(commissions) > 1:
            action['domain'] = [('id', 'in', commissions.ids)]
        elif len(commissions) == 1:
            form_view = [(self.env.ref('sale.view_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = commissions.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action

    def action_view_sale_root(self, sales=False):
        if not sales:
            sales = self.mapped('sale_ids')
        action = self.env['ir.actions.actions']._for_xml_id('sale.action_quotations_with_onboarding')
        if len(sales) > 1:
            action['domain'] = [('id', 'in', sales.ids)]
        elif len(sales) == 1:
            form_view = [(self.env.ref('sale.view_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = sales.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action

    def create_commission(self):
        ProductProduct = self.env['product.product']
        group_partner = {}
        for order in self:
            if (order.partner_id, order.currency_id) not in group_partner:
                group_partner.update({(order.partner_id, order.currency_id): [order]})
            else:
                group_partner[(order.partner_id, order.currency_id)].append(order)
        for partner in group_partner.keys():
            sale_orders = group_partner[partner]
            value_delivery = 0
            move_assign_commission_ids = self.env['stock.move']
            for sale_order in sale_orders:
                for order_line in sale_order.order_line:
                    if order_line.purchase_line_ids.order_id.picking_ids.filtered(
                            lambda p: p.is_dropship):
                        move_ids = order_line.purchase_line_ids.move_ids.filtered(
                            lambda x: not x.sale_line_commission_id
                            and x.picking_id.picking_type_code == 'dropship'
                            and x.state == 'done')
                        if move_ids:
                            qty = sum(move_ids.mapped('quantity'))
                            value_delivery += (qty * order_line.price_unit)
                            move_assign_commission_ids |= move_ids
                    elif order_line.move_ids:
                        move_ids = order_line.move_ids.filtered(lambda x: not x.sale_line_commission_id
                                                                and x.picking_id.picking_type_code == 'outgoing'
                                                                and x.state == 'done')
                        if move_ids:
                            qty = sum(move_ids.mapped('quantity'))
                            value_delivery += (qty * order_line.price_unit)
                            move_assign_commission_ids |= move_ids
                    elif not order_line.move_ids and order_line.purchase_line_ids.order_id.picking_ids.filtered(
                            lambda p: p.is_dropship):
                        move_ids = order_line.purchase_line_ids.move_ids.filtered(
                            lambda x: not x.sale_line_commission_id
                            and x.picking_id.picking_type_code == 'dropship'
                            and x.state == 'done')
                        if move_ids:
                            qty = sum(move_ids.mapped('quantity'))
                            value_delivery += (qty * order_line.price_unit)
                            move_assign_commission_ids |= move_ids
            if not move_assign_commission_ids:
                continue
            if sale_orders:
                tag = self.env.ref('soa_sale_management.crm_tag_buying_office', False)
                sale_commission = sale_orders[0].copy({
                    'order_line': False,
                    'is_sale_commission': True,
                    'payment_term_id': False,
                    'tag_ids': [(6, 0, tag.ids)] if tag else False,
                    'sale_ids': [(6, 0, [x.id for x in sale_orders])],
                    'analytic_account_id': sale_orders[0].analytic_account_id.id or False,
                })
                if sale_commission:
                    product = ProductProduct.search([('detailed_type', '=', 'service'), ('commission_fee', '=', True)],
                                                    limit=1)
                    if not product:
                        raise ValidationError(_("The product 'Commission fee' does not exist."))
                    vals = self._prepare_sale_commission_line(product, value_delivery, move_assign_commission_ids)
                    sale_commission.order_line = [(0, 0, vals)]

    def _prepare_sale_commission_line(self, product, value_delivery, move_assign_commission_ids):
        vals = {
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': value_delivery,
            'commission_move_ids': [(6, 0, move_assign_commission_ids.ids)]
        }
        return vals
