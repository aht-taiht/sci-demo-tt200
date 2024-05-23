# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from datetime import datetime
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

AA_SEQUENCE_PADDING = 2


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    analytic_plan_id = fields.Many2one('account.analytic.plan', 'Business Unit')
    customer_code = fields.Char(related='partner_id.customer_code')

    def _prepare_analytic_account_data(self, prefix=None):
        # Override base method
        result = super(SaleOrder, self)._prepare_analytic_account_data(prefix=prefix)
        commercial_partner = self.partner_id.commercial_partner_id
        if self.analytic_plan_id:
            result['plan_id'] = self.analytic_plan_id.id
        else:
            raise UserError(_('You must set the Analytic plan in the Sales Order first !'))
        if not commercial_partner.customer_code:
            raise UserError(_('You must set the Code for the customer "%s" first !', self.partner_id.display_name))

        affective_date = fields.Date.today()
        # Get the index of the project of this customer
        project_index_line = commercial_partner.get_project_index_line(affective_date)
        project_index = (project_index_line.current_project_index or 0) + 1
        project_index_str = '%%0%sd' % AA_SEQUENCE_PADDING % project_index

        name = commercial_partner.customer_code + affective_date.strftime('%y') + project_index_str
        result['name'] = name
        return result

    def _action_confirm(self):
        result = super(SaleOrder, self)._action_confirm()

        for order in self:
            if not order.analytic_plan_id and order.analytic_account_id:
                order.analytic_plan_id = order.analytic_account_id.plan_id
            if not order.analytic_plan_id and order.order_line:
                raise UserError(_('You must set the Analytic plan in the Sales Order first !'))

        return result

    def _get_number_partner_analytic(self, partner_id, current_date, analytic_id, order_id=None):
        if current_date:
            current_date = datetime.strptime(str(current_date), '%Y-%m-%d %H:%M:%S').date()
        else:
            current_date = datetime.strptime(str(fields.Datetime.now()), '%Y-%m-%d %H:%M:%S').date()

        year = current_date.year
        domain = [
            ('partner_id', 'parent_of', partner_id),
            ('analytic_id', '=', analytic_id),
            ('year', '=', year)
        ]

        indexObj = self.env['partner.analytic.index']

        analytic_index = indexObj.search(domain)
        partner = self.env['res.partner'].browse(partner_id)
        if not analytic_index:
            analytic_index = indexObj.create({
                'partner_id': partner.commercial_partner_id.id, 'analytic_id': analytic_id, 'year': year
            })

        analytic_index.current_index += 1
        return "{0:02d}".format(analytic_index.current_index)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                if vals.get('analytic_account_id', False):
                    analytic_account = self.env['account.analytic.account'].browse(vals.get('analytic_account_id'))
                    number = self._get_number_partner_analytic(
                        vals.get('partner_id'), vals.get('date_order', False), vals.get('analytic_account_id'))
                    vals['name'] = "{}-{}-PI".format(analytic_account.name, number)

        orders = super(SaleOrder, self).create(vals_list)
        no_aa_orders = orders.filtered(lambda o: not o.analytic_account_id)
        for order in no_aa_orders:
            # if any(expense_policy not in [False, 'no'] for expense_policy in order.order_line.product_id.mapped('expense_policy')):
            #     if not order.analytic_account_id:
            #         order._create_analytic_account()
            #         _logger.info('-' * 15 + 'order.analytic_account_id: %s', order.analytic_account_id)
            # if order.analytic_account_id:
            # analytic_account = order.analytic_account_id
            # partner = order.partner_id
            # number = order._get_number_partner_analytic(partner, str(order.date_order), analytic_account)
            # order.name = "{}-{}-PI".format(analytic_account.name, number)
            order.name = _("New")
        return orders

    def _action_confirm(self):
        res = super(SaleOrder, self)._action_confirm()
        for order in self:
            if order.analytic_account_id and (order.name == _("New") or order.name == _("Mới")):
                analytic_account = order.analytic_account_id
                number = order._get_number_partner_analytic(
                    order.partner_id.id, str(order.date_order), analytic_account.id, order.id)
                order.name = "{}-{}-PI".format(analytic_account.name, number)
                if order.picking_ids:
                    order.picking_ids.write({'origin': order.name})
        return res
