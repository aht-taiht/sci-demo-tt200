# -*- coding: utf-8 -*-
import lxml.html

from odoo import models, api, fields, _
from odoo.addons.sale_project.models.sale_order import SaleOrder as SaleOrderProject


class SOProjectInherit(SaleOrderProject):
    _inherit = 'sale.order'

    # Override: task MASOA2301ERPMT-2
    @api.model_create_multi
    def create(self, vals_list):
        created_records = super(SaleOrderProject, self).create(vals_list)
        project = self.env['project.project'].browse(self.env.context.get('create_for_project_id'))
        if project:
            service_sol = next((sol for sol in created_records.order_line), False)
            if service_sol:
                if not project.sale_line_id:
                    project.sale_line_id = service_sol
        return created_records


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    etd_order = fields.Date(string='ETD', copy=False)
    atd_order = fields.Date(string='ATD', copy=False)
    email = fields.Char(string='Email', related='partner_id.email')
    tel = fields.Char(string='Tel', related='partner_id.phone')
    forwarder = fields.Text(string='Forwarder', copy=False)
    po_no = fields.Char(string='Po.No', copy=False)
    cbm = fields.Char(string='CBM', copy=False)
    country_of_origin = fields.Char('Country Of Origin', copy=False)
    port_of_discharge = fields.Char('Port Of Discharge', copy=False)
    port_of_loading = fields.Char('Port Of Loading', copy=False)
    const = fields.Char('Container', copy=False)
    const_type = fields.Char('Container Type', copy=False)
    seal = fields.Char('Seal', copy=False)
    legal = fields.Char('Legal', copy=False)
    delivery_term = fields.Char(string='Delivery Term')
    report_cbm = fields.Float(compute='_compute_report_cbm')
    receiver_note = fields.Text(string='Receiver Note')

    def _compute_report_cbm(self):
        for order in self:
            order.report_cbm = sum(self.order_line.filtered(lambda l: not l.display_type).mapped('volume_export'))

    def create_purchase_order(self):
        for order in self:
            order.order_line.filtered(lambda x: not x.display_type).sudo()._purchase_generation()

    def get_amount_deposit_1st(self):
        if not self.payment_term_id:
            return 0.0
        terms = self.payment_term_id._compute_terms(
            date_ref=self.date_order or fields.Date.context_today(self),
            currency=self.currency_id,
            company=self.company_id,
            tax_amount=self.currency_id._convert(
                self.amount_tax, self.company_id.currency_id, self.company_id, self.date_order),
            tax_amount_currency=self.amount_tax,
            untaxed_amount=self.currency_id._convert(
                self.amount_untaxed, self.company_id.currency_id, self.company_id, self.date_order),
            untaxed_amount_currency=self.amount_untaxed,
            sign=1)
        terms_lines = sorted(terms["line_ids"], key=lambda t: t.get('date'))
        if terms_lines and terms_lines[0]:
            if self.currency_id == self.company_id.currency_id:
                amount = terms_lines[0]['company_amount']
            else:
                amount = terms_lines[0]['foreign_amount']
            return amount
        return 0.0

    def has_note_content(self):
        document = lxml.html.document_fromstring(self.note or '<div></div>')
        content = document.text_content() or ''
        return bool(content.encode("ascii", "ignore").decode().strip())

    def _field_titles(self):
        return {
            'bank': 'Bank: ' if 'source' in self.company_id.name.lower() else 'Beneficiary’s bank: ',
            'account': 'Account Number: ' if 'source' in self.company_id.name.lower() else 'Beneficiary’s account:'
        }

    def _action_confirm(self):
        res = super(SaleOrder, self)._action_confirm()
        if len(self.company_id) == 1:
            self.order_line.sudo().with_company(self.company_id)._timesheet_storable_generation()
        else:
            for order in self:
                self.order_line.sudo().with_company(order.company_id)._timesheet_storable_generation()

        for order in self:
            purchase_order_id = order.order_line.purchase_line_ids.order_id
            if order.analytic_account_id and purchase_order_id and not purchase_order_id.analytic_account_id:
                purchase_order_id.analytic_account_id = order.analytic_account_id
        return res

    # task MASOA2301ERPMT-24
    # override
    def _compute_show_project_and_task_button(self):
        is_project_manager = self.env.user.has_group('project.group_project_manager')
        show_button_ids = self.env['sale.order.line']._read_group([
            ('order_id', 'in', self.ids),
            ('order_id.state', 'not in', ['draft', 'sent']),
            ('product_id.detailed_type', 'in', ['service', 'product']),
        ], aggregates=['order_id:array_agg'])[0][0]
        for order in self:
            order.show_project_button = order.id in show_button_ids and order.project_count
            order.show_task_button = order.show_project_button or order.tasks_count
            order.show_create_project_button = is_project_manager and order.id in show_button_ids and not order.project_count and order.order_line.product_template_id.filtered(
                lambda x: x.service_policy in ['delivered_timesheet', 'delivered_milestones'])

    # override
    def action_view_project_ids(self):
        self.ensure_one()
        if not self.order_line:
            return {'type': 'ir.actions.act_window_close'}

        sorted_line = self.order_line.sorted('sequence')
        default_sale_line = next(sol for sol in sorted_line if sol.product_id.detailed_type in ['service', 'product'])
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Projects'),
            'domain': ['|', ('sale_order_id', '=', self.id), ('id', 'in', self.with_context(active_test=False).project_ids.ids), ('active', 'in', [True, False])],
            'res_model': 'project.project',
            'views': [(False, 'kanban'), (False, 'tree'), (False, 'form')],
            'view_mode': 'kanban,tree,form',
            'context': {
                **self._context,
                'default_partner_id': self.partner_id.id,
                'default_sale_line_id': default_sale_line.id,
                'default_allow_billable': 1,
            }
        }
        if len(self.with_context(active_test=False).project_ids) == 1:
            action.update({'views': [(False, 'form')], 'res_id': self.project_ids.id})
        return action


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_data_to_xlsx_report(self):
        pkg_type = self.product_packaging_id.package_type_id

        results = {
            'customer_item_no': self.customer_item_no or '',
            'supplier_item_no': self.supplier_item_no or '',
            'picture': '',
            'description': self.name,
            'material': self.product_id.product_tmpl_id.material or '',
            'colour': self.product_id.product_tmpl_id.color or '',
            'product__W': self.product_id.product_tmpl_id.w_cm or '',
            'product__L': self.product_id.product_tmpl_id.l_cm or '',
            'product__H': self.product_id.product_tmpl_id.h_cm or '',
            'product__hs_code': self.product_id.product_tmpl_id.hs_code or '',
            'product__quantity': self.product_uom_qty,
            'product__unit_price': self.price_unit,
            'product__total_amount': self.price_subtotal,
            'pkg_inner_box__W': pkg_type.width if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__L': pkg_type.packaging_length if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__H': pkg_type.height if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__qty_per_inner_box': self.product_packaging_qty if pkg_type.type_packing == 'inner_box' else None,
            'pkg_inner_box__total_inner_box': (
                self.product_uom_qty / self.product_packaging_qty if self.product_packaging_qty else 0.0)
            if pkg_type.type_packing == 'inner_box' else None,
            'pkg_masterbox__W': pkg_type.width if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__L': pkg_type.packaging_length if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__H': pkg_type.height if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__qty_per_export': self.product_packaging_qty if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__total_export': self.product_packaging_qty if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__nw': pkg_type.nw_packing if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__gw': pkg_type.gw_packing if pkg_type.type_packing == 'master_box' else None,
            'pkg_masterbox__volume_per_export': pkg_type.width * pkg_type.packaging_length * pkg_type.height / 1000000,
            'pkg_masterbox__total_volume': 0.0,
            'pkg_giftbox__W': pkg_type.width if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__L': pkg_type.packaging_length if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__H': pkg_type.height if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__qty_per_pallet': self.product_packaging_qty if pkg_type.type_packing == 'pallet' else None,
            'pkg_giftbox__total_pallet': (self.product_uom_qty / self.product_packaging_qty
                                          if self.product_packaging_qty else 0.0)
            if pkg_type.type_packing == 'pallet' else None,
        }
        results['pkg_masterbox__total_volume'] = results['pkg_masterbox__volume_per_export'] * self.product_packaging_qty
        return results
