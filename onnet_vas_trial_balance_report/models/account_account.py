# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    follow_by_partner = fields.Boolean(string='Is follow by partner?', default=False)