# -*- coding: utf-8 -*-

from odoo import models, api, fields, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_code = fields.Char('Customer Code')
    account_client_code = fields.Char(string='Account Client Code')
    sector_industry = fields.Text(string='Sector Industry')
    sub_sector = fields.Text(string='Sub Sector')
    activity = fields.Text(string='Activity')

    # Accounting
    property_account_payable_id = fields.Many2one(
        domain="[('account_type', 'in', ('liability_payable', 'asset_current')), ('deprecated', '=', False)]")
    property_account_receivable_id = fields.Many2one(
        domain="[('account_type', 'in', ('asset_receivable', 'asset_current')), ('deprecated', '=', False)]")

    _sql_constraints = [
        ('customer_code_unique', 'unique(customer_code)', 'A partner with the same code already exists !')
    ]
