# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountGroup(models.Model):
    _inherit = 'account.group'
    
    account_ids = fields.One2many('account.account', 'group_id', string='Accounts', copy=False, readonly=True)