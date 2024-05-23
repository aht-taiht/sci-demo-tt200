# -*- coding: utf-8 -*-

from odoo import models, api, fields, _


class AccountPaymentWizard(models.TransientModel):
    _name = 'account.payment.wizard'
    _inherit = 'analytic.mixin'

    journal_id = fields.Many2one('account.journal', compute='_compute_journal_id', store=True, readonly=False,
                                 precompute=True, check_company=True, domain="[('id', 'in', available_journal_ids)]")
    available_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_available_journal_ids'
    )
    payment_type = fields.Selection([
        ('outbound', 'Send Money'),
        ('inbound', 'Receive Money'),
    ], string='Payment Type', copy=False)
    partner_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Vendor'),
    ], default='customer')
    payment_date = fields.Date(string="Payment Date", required=True,
                               default=fields.Date.context_today)
    communication = fields.Char(string="Memo")

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        compute='_compute_currency_id', store=True, readonly=False, precompute=True,
        help="The payment's currency.")
    amount = fields.Monetary(currency_field='currency_id', store=True, readonly=False,
                             compute='_compute_amount')
    partner_id = fields.Many2one('res.partner',
                                 string="Customer/Vendor", ondelete='restrict')
    partner_bank_id = fields.Many2one(
        comodel_name='res.partner.bank',
        string="Recipient Bank Account"
    )
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Payment Method', readonly=False,
                                             store=True,
                                             compute='_compute_payment_method_line_id',
                                             domain="[('id', 'in', available_payment_method_line_ids)]")
    available_payment_method_line_ids = fields.Many2many('account.payment.method.line',
                                                         compute='_compute_payment_method_line_fields')

    @api.depends('journal_id')
    def _compute_currency_id(self):
        for wizard in self:
            wizard.currency_id = wizard.journal_id.currency_id or wizard.company_id.currency_id

    def create_payment(self):
        payment_vals = self._prepare_payment_value()
        self.env['account.payment'].create(payment_vals)

    @api.depends('company_id')
    def _compute_available_journal_ids(self):
        for wizard in self:
            wizard.available_journal_ids = self.env['account.journal'].search([
                *self.env['account.journal']._check_company_domain(wizard.company_id),
                ('type', 'in', ('bank', 'cash')),
            ])

    @api.depends('available_journal_ids')
    def _compute_journal_id(self):
        for wizard in self:
            wizard.journal_id = self.env['account.journal'].search([
                *self.env['account.journal']._check_company_domain(wizard.company_id),
                ('type', 'in', ('bank', 'cash')),
                ('id', 'in', self.available_journal_ids.ids)
            ], limit=1)

    @api.depends('payment_type', 'journal_id', 'currency_id')
    def _compute_payment_method_line_fields(self):
        for wizard in self:
            if wizard.journal_id:
                wizard.available_payment_method_line_ids = wizard.journal_id._get_available_payment_method_lines(
                    wizard.payment_type)
            else:
                wizard.available_payment_method_line_ids = False

    @api.depends('payment_type', 'journal_id')
    def _compute_payment_method_line_id(self):
        for wizard in self:
            if wizard.journal_id:
                available_payment_method_lines = wizard.journal_id._get_available_payment_method_lines(
                    wizard.payment_type)
            else:
                available_payment_method_lines = False

            # Select the first available one by default.
            if available_payment_method_lines:
                wizard.payment_method_line_id = available_payment_method_lines[0]._origin
            else:
                wizard.payment_method_line_id = False

    def _prepare_payment_value(self):
        payment_vals = {
            'date': self.payment_date,
            'amount': self.amount,
            'payment_type': self.payment_type,
            'partner_type': self.partner_type,
            'ref': self.communication,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'partner_bank_id': self.partner_bank_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'analytic_distribution': self.analytic_distribution or False
        }
        if self._context.get('active_model') == 'sale.order':
            payment_vals['sale_order_id'] = self._context.get('active_id')
        if self._context.get('active_model') == 'purchase.order':
            payment_vals['purchase_order_id'] = self._context.get('active_id')
        return payment_vals
