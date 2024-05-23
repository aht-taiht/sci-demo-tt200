# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.tools import format_date, formatLang, frozendict, date_utils

from dateutil.relativedelta import relativedelta


class AccountPaymentTermLine(models.Model):
    _inherit = 'account.payment.term.line'

    delay_type = fields.Selection(selection_add=[('days_after_etd', 'After ETD'), ('days_after_atd', 'After ATD'),
                                                 ('days_after_order', 'After Order Date')],
                                  ondelete={'days_after_etd': 'cascade',
                                            'days_after_atd': 'cascade',
                                            'days_after_order': 'cascade'})
