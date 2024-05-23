# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from datetime import datetime
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _get_number_partner_analytic(self, partner_id, current_date, analytic_id, order_id=None):
        if current_date:
            current_date = datetime.strptime(
                str(current_date), '%Y-%m-%d %H:%M:%S').date()
        else:
            current_date = datetime.strptime(
                str(fields.Datetime.now()), '%Y-%m-%d %H:%M:%S').date()

        year = current_date.year
        domain = [
            ('partner_id', 'parent_of', partner_id),
            ('analytic_id', '=', analytic_id),
            ('year', '=', year)
        ]

        indexObj = self.env['partner.purchase.analytic.index']

        analytic_index = indexObj.search(domain)
        if not analytic_index:
            analytic_index = indexObj.create({
                'partner_id': partner_id, 'analytic_id': analytic_id, 'year': year
            })

        analytic_index.current_index += 1
        return "{0:02d}".format(analytic_index.current_index)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                if vals.get('analytic_account_id', False):
                    analytic_account = self.env['account.analytic.account'].browse(
                        vals.get('analytic_account_id'))
                    number = self._get_number_partner_analytic(
                        vals.get('partner_id'), vals.get('date_order', False), vals.get('analytic_account_id'))
                    vals['name'] = "{}-{}-PO".format(analytic_account.name, number)

        res = super(PurchaseOrder, self).create(vals_list)
        # if Purchase Order not assigned Account Analytic, set name = 'New
        for order in res:
            if not order.analytic_account_id and order.state in ['draft', 'sent', 'to approve']:
                order.name = _("New")
        return res

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        for order in self:
            if order.analytic_account_id and (order.name == _("New") or order.name == _("Mới")):
                analytic_account = order.analytic_account_id
                partner = order.partner_id
                number = order._get_number_partner_analytic(
                    partner.id, str(order.date_order), analytic_account.id, order.id)
                order.name = "{}-{}-PO".format(analytic_account.name, number)
                if order.picking_ids:
                    order.picking_ids.write({'origin': order.name})
            elif order.name == _("New") or order.name == _("Mới"):
                self_comp = self.with_company(order.company_id)
                order.name = self_comp.env['ir.sequence'].next_by_code(
                    'purchase.order', sequence_date=order.date_order) or _("New")
        return res
