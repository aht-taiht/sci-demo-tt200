# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    margin = fields.Float(string='Margin')
    hidden_margin = fields.Float(string='Hidden Margin')
    image = fields.Image(string='Image', related='product_id.image_1920')
    customer_item_no = fields.Char(string='Customer Item No', related='product_id.customer_code')
    supplier_item_no = fields.Char(string='Supplier Item No', related='product_id.supplier_code')
    product_litre_qty = fields.Float(string="Litre Quantity")

    # Sourcing info
    package_type_id = fields.Many2one(related='product_packaging_id.package_type_id')
    material = fields.Char(related='product_template_id.material')
    color = fields.Char(related='product_template_id.color')
    w_cm = fields.Float(related='product_template_id.w_cm')
    h_cm = fields.Float(related='product_template_id.h_cm')
    l_cm = fields.Float(related='product_template_id.l_cm')
    hs_code = fields.Char(related='product_template_id.hs_code')

    package_w_cm = fields.Float(related='package_type_id.width', string="W (cm) Package")
    package_h_cm = fields.Float(related='package_type_id.height', string="H (cm) Package")
    package_l_cm = fields.Float(related='package_type_id.packaging_length', string="L (cm) Package")
    nw_packing = fields.Float(related='package_type_id.nw_packing', string="NW (kg)")
    gw_packing = fields.Float(related='package_type_id.gw_packing', string="GM (kg)")
    volume_export = fields.Float(compute='_compute_volume', string="Volume Per Export (cbm)")
    total_volume = fields.Float(compute='_compute_volume', string="Total Volume (cbm)")
    price_unit_inl_tax = fields.Float(string='Unit Price Incl Tax', compute='_compute_price_unit_inl_tax')

    def _compute_price_unit_inl_tax(self):
        for line in self:
            if line.product_uom_qty:
                line.price_unit_inl_tax = line.price_total / line.product_uom_qty
            else:
                tax_base_line_dict = line._convert_to_tax_base_line_dict()
                tax_base_line_dict['quantity'] = 1
                tax_results = self.env['account.tax']._compute_taxes([
                    tax_base_line_dict
                ])
                totals = list(tax_results['totals'].values())[0]
                amount_untaxed = totals['amount_untaxed']
                amount_tax = totals['amount_tax']
                line.price_unit_inl_tax = amount_untaxed + amount_tax

    @api.depends('package_h_cm', 'package_w_cm', 'package_l_cm')
    def _compute_volume(self):
        for line in self:
            volume_export = line.package_w_cm * line.package_h_cm * line.package_l_cm / 1_000_000
            line.volume_export = volume_export
            line.total_volume = volume_export * line.product_packaging_qty

    # Inherit method
    def _purchase_service_prepare_order_values(self, supplierinfo):
        result = super()._purchase_service_prepare_order_values(supplierinfo)
        if self.order_id.analytic_account_id:
            result['analytic_account_id'] = self.order_id.analytic_account_id.id
        return result

    def _purchase_generation(self):
        sale_line_purchase_map = {}
        for line in self:
            free_qty = 0
            if not line.display_type:
                free_qty = self.env['stock.quant']._get_available_quantity(line.product_id,
                                                                           line.warehouse_id.lot_stock_id)
            if line.move_ids:
                quantity = sum(
                    line.move_ids.filtered(lambda x: x.picking_id.picking_type_code == 'outgoing').mapped('quantity'))
                free_qty += quantity

            qty_can_order = 0
            if line.product_uom_qty > free_qty:
                qty_can_order = line.product_uom_qty - free_qty
            # if not line.purchase_line_count:
            if qty_can_order:
                result = line._purchase_no_merge_service_create(quantity=qty_can_order)
                sale_line_purchase_map.update(result)
        return sale_line_purchase_map

    def _purchase_service_no_merge_prepare_line_values(self, purchase_order, quantity=False):
        """ Returns the values to create the purchase order line from the current SO line.
            :param purchase_order: record of purchase.order
            :rtype: dict
            :param quantity: the quantity to force on the PO line, expressed in SO line UoM
        """
        self.ensure_one()
        # compute quantity from SO line UoM
        product_quantity = self.product_uom_qty
        if quantity:
            product_quantity = quantity

        purchase_qty_uom = self.product_uom._compute_quantity(product_quantity, self.product_id.uom_po_id)

        # determine vendor (real supplier, sharing the same partner as the one from the PO, but with more accurate informations like validity, quantity, ...)
        # Note: one partner can have multiple supplier info for the same product
        supplierinfo = self.product_id._select_seller(
            partner_id=purchase_order.partner_id,
            quantity=purchase_qty_uom,
            date=purchase_order.date_order and purchase_order.date_order.date(),  # and purchase_order.date_order[:10],
            uom_id=self.product_id.uom_po_id
        )

        price_unit, taxes = self._purchase_service_get_price_unit_and_taxes(supplierinfo, purchase_order)
        name = self._purchase_service_get_product_name(supplierinfo, purchase_order, quantity)

        line_description = self.with_context(
            lang=self.order_id.partner_id.lang)._get_sale_order_line_multiline_description_variants()
        if line_description:
            name += line_description

        return {
            'name': name,
            'product_qty': purchase_qty_uom,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_po_id.id,
            'price_unit': price_unit,
            'date_planned': purchase_order.date_order + relativedelta(days=int(supplierinfo.delay)),
            'taxes_id': [(6, 0, taxes.ids)],
            'order_id': purchase_order.id,
            'sale_line_id': self.id,
            'analytic_distribution': self.analytic_distribution
        }

    def _purchase_no_merge_service_create(self, quantity=False):
        """ On Sales Order confirmation, some lines (services ones) can create a purchase order line and maybe a purchase order.
            If a line should create a RFQ, it will check for existing PO. If no one is find, the SO line will create one, then adds
            a new PO line. The created purchase order line will be linked to the SO line.
            :param quantity: the quantity to force on the PO line, expressed in SO line UoM
        """
        supplier_po_map = {}
        sale_line_purchase_map = {}

        for line in self:
            line = line.with_company(line._purchase_service_get_company())
            supplierinfo = line._purchase_service_match_supplier()
            partner_supplier = supplierinfo.partner_id

            # determine (or create) PO
            purchase_order = supplier_po_map.get(partner_supplier.id)
            if not purchase_order:
                purchase_order = line._match_or_create_purchase_order_no_merge(supplierinfo)
            else:  # if not already updated origin in this loop
                so_name = line.order_id.name
                origins = (purchase_order.origin or '').split(', ')
                if so_name not in origins:
                    purchase_order.write({'origin': ', '.join(origins + [so_name])})
            supplier_po_map[partner_supplier.id] = purchase_order

            # add a PO line to the PO
            values = line._purchase_service_no_merge_prepare_line_values(purchase_order, quantity=quantity)
            purchase_line = line.env['purchase.order.line'].create(values)

            # link the generated purchase to the SO line
            sale_line_purchase_map.setdefault(line, line.env['purchase.order.line'])
            sale_line_purchase_map[line] |= purchase_line
        return sale_line_purchase_map

    def _match_or_create_purchase_order_no_merge(self, supplierinfo):
        purchase_order = False
        purchase_orders = self._purchase_service_match_purchase_order_no_merge(supplierinfo.partner_id)
        if purchase_orders:
            purchase_order = purchase_orders[:1]
        if not purchase_order:
            purchase_order = self._create_purchase_order(supplierinfo)
        return purchase_order

    def _purchase_service_match_purchase_order_no_merge(self, partner, company=False):
        purchases = self.env['purchase.order'].search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'draft'),
            ('company_id', '=', (company and company or self.env.company).id),
        ], order='id desc')
        if self.order_id not in purchases.mapped('order_line.sale_order_id'):
            return False
        return purchases

    def _timesheet_create_project_storable_prepare_values(self):
        """Generate project values"""
        account = self.order_id.analytic_account_id
        if not account:
            service_products = self.order_id.order_line.product_id.filtered(
                lambda p: p.type == 'product' and p.default_code)
            default_code = service_products.default_code if len(service_products) == 1 else None
            self.order_id._create_analytic_account(prefix=default_code)
            account = self.order_id.analytic_account_id
        # create the project or duplicate one
        return {
            'name': '%s - %s' % (self.order_id.client_order_ref, self.order_id.name) if self.order_id.client_order_ref else self.order_id.name,
            'analytic_account_id': account.id,
            'partner_id': self.order_id.partner_id.id,
            'sale_line_id': self.id if self.is_service else False,
            'active': True,
            'company_id': self.company_id.id,
            'allow_billable': True,
            'user_id': False,
        }

    def _timesheet_create_project_storable(self):
        """ Generate project for the given so line, and link it.
            :param project: record of project.project in which the task should be created
            :return task: record of the created task
        """
        self.ensure_one()
        values = self._timesheet_create_project_storable_prepare_values()

        if self.product_id.project_template_id:
            values['name'] = "%s - %s" % (values['name'], self.product_id.project_template_id.name)
            # The no_create_folder context key is used in documents_project
            project = self.product_id.project_template_id.with_context(no_create_folder=True).copy(values)
            project.tasks.write({
                'sale_line_id': self.id,
                'partner_id': self.order_id.partner_id.id,
            })
            # duplicating a project doesn't set the SO on sub-tasks
            project.tasks.filtered('parent_id').write({
                'sale_line_id': self.id,
                'sale_order_id': self.order_id.id,
            })
        else:
            project_only_sol_count = self.env['sale.order.line'].search_count([
                ('order_id', '=', self.order_id.id),
                ('product_id.type', '=', 'product'),
            ])
            if project_only_sol_count == 1:
                values['name'] = "%s - [%s] %s" % (values['name'], self.product_id.default_code,
                                                   self.product_id.name) if self.product_id.default_code else "%s - %s" % (values['name'], self.product_id.name)
            # The no_create_folder context key is used in documents_project
            project = self.env['project.project'].with_context(no_create_folder=True).create(values)

        # Avoid new tasks to go to 'Undefined Stage'
        if not project.type_ids:
            project.type_ids = self.env['project.task.type'].create([{
                'name': name,
                'fold': fold,
                'sequence': sequence,
            } for name, fold, sequence in [
                (_('To Do'), False, 5),
                (_('In Progress'), False, 10),
                (_('Done'), True, 15),
                (_('Canceled'), True, 20),
            ]])

        # link project as generated by current so line
        self.write({'project_id': project.id})
        return project

    def _timesheet_storable_generation(self):
        so_line_storable_project = self.filtered(lambda sol: sol.product_id.type in ('product', 'consu'))
        map_so_project = {}
        if so_line_storable_project:
            order_ids = self.mapped('order_id').ids
            so_lines_storable_with_project = self.search([('order_id', 'in', order_ids), ('project_id', '!=', False),
                                                 ('product_id.project_template_id', '=', False)])
            map_so_project = {sol.order_id.id: sol.project_id for sol in so_lines_storable_with_project}
            so_lines_with_project_templates = self.search([('order_id', 'in', order_ids), ('project_id', '!=', False),
                                                           ('product_id.project_template_id', '!=', False)])
            map_so_project_templates = {(sol.order_id.id, sol.product_id.project_template_id.id): sol.project_id for sol
                                        in so_lines_with_project_templates}

        map_sol_project = {}

        def _can_create_storable_project(sol):
            if not sol.project_id:
                if sol.product_id.project_template_id:
                    return (sol.order_id.id, sol.product_id.project_template_id.id) not in map_so_project_templates
                elif sol.order_id.id not in map_so_project:
                    return True
            return False

        def _determine_storable_project(so_line):

            # Find the project by the analytic account on Sale Order
            analytic_account_id = so_line.order_id.analytic_account_id
            if analytic_account_id:
                existed_project = self.env['project.project'].search(
                    [('analytic_account_id', '=', analytic_account_id.id)], limit=1)
                if existed_project:
                    if so_line.product_id.type == 'product' and not so_line.project_id:
                        so_line.project_id = existed_project
                    return existed_project

            if so_line.product_id.type == 'product':
                return so_line.project_id

            return False

        # project_only, task_in_project: create a new project, based or not on a template (1 per SO). May be create a task too.
        # if 'task_in_project' and project_id configured on SO, use that one instead
        for so_line in so_line_storable_project:
            project = _determine_storable_project(so_line)
            if not project and _can_create_storable_project(so_line):
                project = so_line._timesheet_create_project_storable()
                if so_line.product_id.project_template_id:
                    map_so_project_templates[
                        (so_line.order_id.id, so_line.product_id.project_template_id.id)] = project
                else:
                    map_so_project[so_line.order_id.id] = project
            elif not project:
                # Attach subsequent SO lines to the created project
                so_line.project_id = (
                    map_so_project_templates.get(
                        (so_line.order_id.id, so_line.product_id.project_template_id.id))
                    or map_so_project.get(so_line.order_id.id)
                )
