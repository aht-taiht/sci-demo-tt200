# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import api, fields, models, _

from odoo.exceptions import UserError

IN_INVOICE = ('in_invoice', 'in_refund', 'in_receipt')
OUT_INVOICE = ('out_invoice', 'out_refund', 'out_receipt')


class AccountMove(models.Model):
    _inherit = 'account.move'

    vat_invoice_date = fields.Datetime(string="Vat invoice date", compute='_compute_vat_invoice_date', store=True)
    vat_invoice_ids = fields.Many2many('account.vat.invoice', string='VAT Invoice', copy=False)
    vat_invoice_count = fields.Integer(compute='_compute_vat_invoice_count')

    vsi_status = fields.Selection([
        ('draft', 'Not yet created'),
        ('created', 'Created'),
        ('canceled', 'Canceled'),
    ], string='VAT-Invoice Status', default='draft', copy=False)

    vat_payment_type = fields.Selection([
        ('1', 'Cash'),
        ('2', 'Bank transfer'),
        ('3', 'Bank transfer / Cash')
    ], string="Payment method", default='3')
    buyer_name = fields.Char('Buyer')
    vsi_number = fields.Char(string="VAT-Invoice No.")

    @api.depends('vat_invoice_ids')
    def _compute_vat_invoice_count(self):
        for move in self:
            move.vat_invoice_count = len(move.vat_invoice_ids)

    @api.depends('vat_invoice_ids.date_invoice', 'vat_invoice_ids.vsi_status')
    def _compute_vat_invoice_date(self):
        for move in self:
            vat_invoice_date = False
            if move.vsi_number:
                vat_invoices = self.env['account.vat.invoice'].sudo().search(
                    [('name', '=', move.vsi_number), ('company_id.id', '=', move.company_id.id)])
                for vat_invoice in vat_invoices:
                    if vat_invoice.vsi_status == 'created':
                        vat_invoice_date = vat_invoice.date_invoice
                        break
                if not vat_invoice_date:
                    vat_invoice_date = move.date
            move.vat_invoice_date = vat_invoice_date

    def create_vat_invoice(self):
        if len(self.vat_invoice_ids) > 0:
            raise UserError("Created VAT Invoice")

        list_tax = []
        list_data = []
        for item in self.invoice_line_ids:
            if item.tax_ids.id not in list_tax:
                list_tax.append(item.tax_ids.id)
                list_data.append({
                    'id_tax': item.tax_ids.id,
                    'invoice_line_id': [item.id]
                })
            if item.tax_ids.id in list_tax:
                for val in list_data:
                    if val['id_tax'] == item.tax_ids.id and \
                            item.id not in val['invoice_line_id']:
                        val['invoice_line_id'].append(item.id)

        list_invoice_create = []
        invoice_line = []
        for invoice in list_data:
            currency = self.currency_id
            for line in invoice['invoice_line_id']:
                invoice_line_id = self.env['account.move.line'].browse(line)
                if invoice_line_id.quantity != 0:
                    data_line = {
                        'product_id': invoice_line_id.product_id.id,
                        'price_subtotal': currency.round(invoice_line_id.price_subtotal),
                        'price_total': currency.round(invoice_line_id.price_total),
                        'quantity': invoice_line_id.quantity,
                        'name': invoice_line_id.name,
                        'invoice_line_tax_ids': invoice_line_id.tax_ids.id,
                        'uom_id': invoice_line_id.product_uom_id.id,
                        'account_move_line_id': invoice_line_id.id
                    }
                    invoice_line.append([0, 0, data_line])
        invoice_data = self._prepare_invoice_data(invoice_line)

        vat_invoice_id = self.env['account.vat.invoice'].create(invoice_data)
        list_invoice_create.append(vat_invoice_id.id)
        self.write({'vat_invoice_ids': [[6, False, list_invoice_create]]})
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.vat.invoice",
            "views": [[False, "form"]],
            "res_id": vat_invoice_id.id,
            "target": "new",
        }

    def _prepare_invoice_data(self, invoice_line):
        partner = self.partner_id
        if not self.partner_id.is_company and self.partner_id.parent_id:
            partner = self.partner_id.parent_id
        partner_address = []
        if partner.street:
            partner_address.append(partner.street)
        if partner.street2:
            partner_address.append(partner.street2)
        if partner.city:
            partner_address.append(partner.city)
        elif partner.state_id:
            partner_address.append(partner.state_id.name)
        address = ', '.join(partner_address)

        invoice_data = {
            'type': self.move_type,
            'partner_id': self.partner_id.id,
            'date_invoice': fields.Datetime.now(),
            'company_id': self.company_id.id,
            'buyer_name': self.buyer_name,
            'user_id': self.user_id.id,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id,
            'payment_type': self.vat_payment_type or '3',
            'invoice_line_ids': invoice_line,
            'amount_untaxed': round(self.amount_untaxed),
            'amount_tax': int(self.amount_tax),
            'amount_total': int(self.amount_total),
            'street_partner': address,
            'date': self.date
        }
        return invoice_data
