# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from num2words import num2words


class AccountVATInvoice(models.Model):
    _name = "account.vat.invoice"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "VAT Invoice"

    name = fields.Char(string="No.", default=_("New"), copy=False)
    type = fields.Selection([
        ('in_invoice', 'In Invoice'),
        ('in_refund', 'Vendor Credit Note'),
        ('out_invoice', 'Out Invoice'),
        ('out_refund', 'Customer Credit Note'),
    ], string="Type", default='in_invoice', copy=False)
    vsi_status = fields.Selection([
        ('draft', 'Draft'),
        ('creating', 'Issuing'),
        ('created', 'Issued'),
        ('canceled', 'Canceled'),
    ], string="Status", default='draft', copy=False, tracking=True)
    date_invoice = fields.Datetime(string="Invoice date")
    # Compute for the previous records. For new record, must set "date" field
    date = fields.Date(
        string='Accounting Date', readonly=False, compute='_compute_accounting_date', store=True, tracking=True)
    payment_term_id = fields.Many2one('account.payment.term', string="Payment term")
    partner_id = fields.Many2one("res.partner", string="Company's name")
    reference = fields.Char()
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string="Currency")
    journal_id = fields.Many2one('account.journal', string="Journal")
    invoice_line_ids = fields.One2many('account.vat.invoice.line', 'invoice_id', string="Product")

    amount_untaxed = fields.Integer(string="Untaxed Amount", compute="_sub_total", store=True, precompute=True)
    amount_tax = fields.Integer(string="Amount tax", compute="_sub_total", store=True, precompute=True)
    amount_total = fields.Integer("Amount total", compute="_sub_total", store=True, precompute=True)
    residual = fields.Integer(string="Residual")

    grossvalue = fields.Float(string="Amount untax")
    grossvalue0 = fields.Float(string="Amount untax 0")
    grossvalue5 = fields.Float(string="Amount untax 5%", compute="_sub_total", store=True, precompute=True)
    grossvalue8 = fields.Float(string="Amount untax 8%", compute="_sub_total", store=True, precompute=True)
    grossvalue10 = fields.Float(string="Amount untax 10%", compute="_sub_total", store=True, precompute=True)
    vatamount5 = fields.Float(string="Amount tax 5%", compute="_sub_total", store=True, precompute=True)
    vatamount8 = fields.Float(string="Amount tax 8%", compute="_sub_total", store=True, precompute=True)
    vatamount10 = fields.Float(string="Amount tax 10%", compute="_sub_total", store=True, precompute=True)

    amountinwords = fields.Char(string="Amount in words", compute="_sub_amount_total", store=True, precompute=True)

    taxRate = fields.Char('GTGT', default="10", compute="_sub_total", store=True, precompute=True, readonly=False,
        help='GTGT, type 10 if 10%, 8 if 8%, 5 if 5%, 0 if 0%, type / if none')

    exchange_rate = fields.Float(string="Exchange Rate", compute="_compute_exchange_rate", readonly=False, store=True)

    user_id = fields.Many2one('res.users', string="User")
    buyer_name = fields.Char(string="Buyer")

    account_move_ids = fields.Many2many("account.move", string="Internal invoice", copy=False)

    # tax_company = fields.Char("Mã số thuế", related="company_branch_id.vsi_tin")
    tax_company = fields.Char(string="Vat", related="company_id.vat")
    street_company = fields.Char(string="Address", related="company_id.street")
    vat_partner = fields.Char("Vat", related="partner_id.vat")
    street_partner = fields.Char("Address")
    email_partner = fields.Char("Email", related="partner_id.email")
    phone_partner = fields.Char("Phone", related="partner_id.phone")

    payment_type = fields.Selection([
        ('1', 'TM'),
        ('2', 'CK'),
        ('3', 'TM/CK'),
        ('4', 'DTCN'),
        ('5', 'KHAC')
    ], string="Payment method", default='3')

    additionalReferenceDesc = fields.Char("Agreement document")
    additionalReferenceDate = fields.Datetime("Agreement date")

    @api.depends('date_invoice')
    def _compute_accounting_date(self):
        for invoice in self.filtered(lambda inv: not inv.date):
            invoice.date = invoice.date_invoice or False

    @api.depends('currency_id')
    def _compute_exchange_rate(self):
        for inv in self:
            exchange_rate = 1
            if inv.currency_id:
                exchange_rate = inv.currency_id.rate
            inv.exchange_rate = exchange_rate

    @api.depends('invoice_line_ids', 'invoice_line_ids.price_total', 'invoice_line_ids.vat_amount', 'invoice_line_ids.price_subtotal')
    def _sub_total(self):
        for inv in self:
            tax = 0
            tax5 = 0
            tax8 = 0
            tax10 = 0
            gross5 = 0
            gross8 = 0
            gross10 = 0
            amount_untaxed = 0
            amount_total = 0
            taxRate = '/'
            for line in inv.invoice_line_ids:
                amount_untaxed += line.price_subtotal
                amount_total += line.price_total
                tax += line.vat_amount
                if line.vat_rate == 5:
                    taxRate = '5'
                    tax5 += line.vat_amount
                    gross5 += line.price_total
                elif line.vat_rate == 8:
                    taxRate = '8'
                    tax8 += line.vat_amount
                    gross8 += line.price_total
                elif line.vat_rate == 10:
                    taxRate = '10'
                    tax10 += line.vat_amount
                    gross10 += line.price_total
                elif line.invoice_line_tax_ids and line.vat_rate == 0:
                    taxRate = '0'
                elif not line.invoice_line_tax_ids:
                    taxRate = '/'

            inv.amount_untaxed = amount_untaxed
            inv.amount_total = amount_total
            inv.amount_tax = inv.amount_total - inv.amount_untaxed
            inv.grossvalue5 = gross5
            inv.grossvalue8 = gross8
            inv.grossvalue10 = gross10
            inv.vatamount5 = tax5
            inv.vatamount8 = tax8
            inv.vatamount10 = tax10
            inv.taxRate = taxRate

    @api.depends('amount_total')
    def _sub_amount_total(self):
        for rec in self:
            rec.amount_total = rec.amount_tax + rec.amount_untaxed
            try:
                rec.amountinwords = num2words(
                    int(rec.amount_total), lang='vi_VN').capitalize() + " đồng chẵn."
            except NotImplementedError:
                rec.amountinwords = num2words(
                    int(rec.amount_total), lang='en').capitalize() + " VND."
