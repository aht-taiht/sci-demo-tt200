# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_etd = fields.Date(string='ETD')
    purchase_atd = fields.Date(string='ATD')
    purchase_no = fields.Char(string='PO.No')
    purchase_cbm = fields.Char(string='CBM')
    forwarder = fields.Char(string='Forwarder')
    country_origin = fields.Char(string='Country of Origin')
    port_discharge = fields.Char(string='Port of Discharge')
    port_loading = fields.Char(string='Port of Loading')
    cont_no = fields.Char(string='Cont. #')
    seal_no = fields.Char(string='SEAL #')
    delivery_term = fields.Char(string='Delivery Term')

    # MASOA2301ERP-83
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Analytic Account")

    report_cbm = fields.Float(compute='_compute_report_cbm')

    user_id = fields.Many2one(default=lambda self: self.env.user)

    def _compute_report_cbm(self):
        for order in self:
            order.report_cbm = sum(self.order_line.filtered(
                lambda l: not l.display_type).mapped('volume_export'))

    def send_deposit_remind_email(self):
        template = self.env.ref(
            'soa_purchase_management.email_template_remind_deposit_of_purchase_order_confirmation')
        template.send_mail(self.id, force_send=True)

    def cron_remind_deposit(self):
        seven_days_ago = datetime.now() - timedelta(days=7)
        cond = [('state', '=', 'purchase'),
                ('date_approve', '>=', seven_days_ago.strftime('%Y-%m-%d %H:00:00')),
                ('date_approve', '<=', seven_days_ago.strftime('%Y-%m-%d %H:59:59'))]
        for po_obj in self.search(cond):
            draft_payment_obj = po_obj.account_payment_ids.filtered(
                lambda x: x.state == 'draft')
            if draft_payment_obj:
                po_obj.send_deposit_remind_email()
