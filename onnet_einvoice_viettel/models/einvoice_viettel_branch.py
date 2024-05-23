# -*- coding: utf-8 -*-

import requests
import logging
from odoo import api, fields, models, _

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
except AttributeError:
    # no pyopenssl support used / needed / available
    pass

_logger = logging.getLogger(__name__)


class EInvoiceViettelBranch(models.Model):
    _name = 'einvoice.viettel.branch'
    _description = 'E-invoice Viettel Branch'

    name = fields.Char(string='Name')
    # code = fields.Char(string='Code')
    # partner_id = fields.Many2one('res.partner', string="Related partner")
    vsi_domain = fields.Char(string="API Domain")
    business_service_domain = fields.Char(string="Business Service Domain")
    portal_service_domain = fields.Char(string="Portal Service Domain")
    vsi_tin = fields.Char(string="VAT", required=True)
    vsi_username = fields.Char(string="Username", required=True)
    vsi_password = fields.Char(string="Password", required=True)
    vsi_token = fields.Char(string="Access Token")
    swap = fields.Boolean(string="Swap CusName/Buyer", default=False)
    vsi_template = fields.Char(string="Form")
    vsi_template_type = fields.Char(string="Form Type")
    vsi_series = fields.Char(string="Series")
    version = fields.Selection([('1', 'API v1'),
                                ('2', 'API v2')], string='API Version', default='1')

    def action_get_token(self):
        authen_url = 'https://api-vinvoice.viettel.vn/auth/login'
        data = {
            'username': self.vsi_username,
            'password': self.vsi_password
        }
        headers = {
            'Content-Type': 'application/json',
        }
        result = requests.post(authen_url, json=data, headers=headers)
        result.raise_for_status()
        if result.json()['access_token']:
            self.vsi_token = result.json()['access_token']
            return result.json()['access_token']
        else:
            return False
