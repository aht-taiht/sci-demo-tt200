# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from num2words import num2words


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    amountinwords = fields.Char(string="Amount in words", compute="_sub_amount_total", store=True, precompute=True)

    @api.depends('amount')
    def _sub_amount_total(self):
        for rec in self:
            try:
                rec.amountinwords = num2words(
                    int(rec.amount), lang='vi_VN').capitalize() + " đồng."
            except NotImplementedError:
                rec.amountinwords = num2words(
                    int(rec.amount), lang='en').capitalize() + " VND."
