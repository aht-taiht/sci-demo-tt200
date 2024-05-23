# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, fields, models, _

from odoo.exceptions import UserError


import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoiceStatus = fields.Selection([
        ('0', "No e-invoice"),
        ('1', "Get e-invoice now"),
        ('2', "Get e-invoice later")
    ], string="E-invoice Status")
    viettel_branch_id = fields.Many2one("einvoice.viettel.branch", string="Viettel Branch")

    vsi_template = fields.Char(string="Form")
    vsi_series = fields.Char(string="Series")
    invoice_address = fields.Char('Invoice address', related="partner_id.street")
    buyer_vat = fields.Char("Buyer vat", related="partner_id.vat")
    viettel_branch_vat = fields.Many2one("einvoice.viettel.branch", string="Viettel Branch Vat")

    def _prepare_invoice_data(self, invoice_line):
        invoice_data = super(AccountMove, self)._prepare_invoice_data(invoice_line)
        invoice_data.update({
            'viettel_branch_id': self.viettel_branch_vat.id,
            'invoiceStatus': self.invoiceStatus,
        })
        return invoice_data

    # # cấm xóa
    # def unlinkForApiUser(self):
    #     if self.env.user.id == 728:     # api@nhanlucsieuviet.com
    #         return super(AccountMove, self.with_context(force_delete=True)).unlink()
    #     else:
    #         return super(AccountMove, self).unlink()
