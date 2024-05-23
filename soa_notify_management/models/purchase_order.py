# -*- coding: utf-8 -*-
from markupsafe import Markup
import logging
from odoo import models, fields, api, _, SUPERUSER_ID
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def send_remind_email(self, template_xml_id):
        template = self.env.ref(template_xml_id)
        template.send_mail(self.id, force_send=True)
        logger.info(f'{self.name} is sent remind email')

    def send_notification(self, template_xml_id, message_body=''):
        template = self.env.ref(template_xml_id)
        if not message_body:
            message_body = template.body_html

        odoobot_id = self.env['ir.model.data'].sudo()._xmlid_to_res_id("base.partner_root")
        partner_ids = [odoobot_id, self.user_id.partner_id.id]
        channel_info = self.env["discuss.channel"].with_user(SUPERUSER_ID).channel_get(partner_ids)
        channel = self.env['discuss.channel'].with_user(SUPERUSER_ID).browse(channel_info['id'])
        channel.message_post(body=Markup(message_body), author_id=odoobot_id, message_type="comment",
                          subtype_xmlid="mail.mt_comment")
    def get_form_url(self):
        action_id = self.env.ref('purchase.purchase_rfq').id
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/web#id={self.id}&action={action_id}&model={self._name}&view_type=form"
        return url

    def get_reminder_body(self, template_xml_id):
        form_url = self.get_form_url()
        template = self.env.ref(template_xml_id)
        message_body = f"{template.body_html} <a href='{form_url}'>{self.name}</a>"
        return message_body

    def cron_remind_deposit(self):
        seven_days_ago = datetime.now() -  timedelta(days=7)
        template_xml_id = 'soa_notify_management.email_template_remind_deposit_of_purchase_order_confirmation'
        cond = [('state', '=', 'purchase'),
                ('date_approve', '>=', seven_days_ago.strftime('%Y-%m-%d %H:00:00')),
                ('date_approve', '<=', seven_days_ago.strftime('%Y-%m-%d %H:59:59'))]
        for po_obj in self.search(cond):
            draft_payment_obj = po_obj.account_payment_ids.filtered(lambda x: x.state=='draft')
            if draft_payment_obj:
                user_id = po_obj.user_id
                if user_id.notification_type == 'email':
                    po_obj.send_remind_email(template_xml_id=template_xml_id)
                else:
                    message_body = po_obj.get_reminder_body(template_xml_id)
                    po_obj.send_notification(template_xml_id=template_xml_id, message_body=message_body)

    def cron_remind_labeling_carton(self):
        """
        Send email to remind after 30 days that Sourcing PO is confirmed
        """
        thirty_days_ago = datetime.today() - timedelta(days=30)
        template_xml_id = \
            'soa_notify_management.email_template_remind_labeling_carton_layout_of_purchase_order_confirmation'
        cond = [('state', '=', 'purchase'),
                ('date_approve', '>=', thirty_days_ago.strftime('%Y-%m-%d %H:00:00')),
                ('date_approve', '<=', thirty_days_ago.strftime('%Y-%m-%d %H:59:59'))]
        for po_obj in self.search(cond):
            sourcing_so_obj = po_obj._get_sale_orders().filtered(lambda x: x.analytic_plan_id.name == 'Sourcing')
            if sourcing_so_obj:
                user_id = po_obj.user_id
                if user_id.notification_type == 'email':
                    po_obj.send_remind_email(template_xml_id=template_xml_id)
                else:
                    message_body = po_obj.get_reminder_body(template_xml_id)
                    po_obj.send_notification(template_xml_id=template_xml_id, message_body=message_body)

    def cron_remind_balance_payment(self):
        """
        Send email to remind after ATD 14 days that Sourcing PO is confirmed
        """
        fourteen_days_ago = datetime.today() - timedelta(days=14)
        template_xml_id = \
            'soa_notify_management.email_template_remind_balance_payment_of_purchase_order_confirmation'
        cond = [('state', '=', 'purchase'),
                ('purchase_atd', '=', fourteen_days_ago.strftime('%Y-%m-%d'))]
        po_objs = self.search(cond)
        for po_obj in po_objs:
            sourcing_so_obj = po_obj._get_sale_orders().filtered(lambda x: x.analytic_plan_id.name == 'Sourcing')
            if sourcing_so_obj:
                user_id = po_obj.user_id
                if user_id.notification_type == 'email':
                    po_obj.send_remind_email(template_xml_id=template_xml_id)
                else:
                    message_body = po_obj.get_reminder_body(template_xml_id)
                    po_obj.send_notification(template_xml_id=template_xml_id, message_body=message_body)
