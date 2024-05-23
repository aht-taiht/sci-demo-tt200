# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    x_payable_account_id = fields.Many2one('account.account', 'Payable Account', company_dependent=True,
                                           help="Account using for transfer account asset")
    x_transfer_journal_id = fields.Many2one('account.journal', 'Transfer Account Journal', company_dependent=True,
                                            help="Journal using for transfer account asset")
