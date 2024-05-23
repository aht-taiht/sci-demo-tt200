# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import ormcache


class AccountAnalyticPlan(models.Model):
    _inherit = 'account.analytic.plan'
