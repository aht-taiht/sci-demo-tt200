# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountAccount(models.Model):
    _inherit = 'account.account'
    
    parent_id = fields.Many2one('account.account')
    child_ids = fields.One2many('account.account', 'parent_id')