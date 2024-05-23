# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _, _lt
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('posted_before', 'state', 'journal_id', 'date', 'move_type', 'payment_id')
    def _compute_name(self):
        self = self.sorted(lambda m: (m.date, m.ref or '', m.id))
        for move in self:
            move_has_name = move.name and move.name != '/'
            if move.date and not move_has_name and move.state == 'posted':
                move._set_next_sequence()
        self.filtered(lambda m: not m.name and not move.quick_edit_mode).name = '/'
        self._inverse_name()

    def _must_check_constrains_date_sequence(self):
        # OVERRIDES account.move
        return self.state == 'posted' and not self.quick_edit_mode and self.journal_id.type != 'sale'

    def _set_next_sequence(self):
        if self.journal_id.type == 'sale':
            self.name = self._compute_customer_inovoice_sequence()
        else:
            if not self.journal_id.sequence_id:
                self.journal_id._create_account_move_seq()
            next_seq = self.journal_id.sequence_id._next(sequence_date=self.date)
            self.name = next_seq

    # def _set_next_sequence(self):
    #     if not self.journal_id.sequence_id:
    #         self.journal_id._create_account_move_seq()
    #     next_seq = self.journal_id.sequence_id._next(sequence_date=self.date)
    #     self.name = next_seq

    def _get_sale_analytic_account(self):
        if not self.invoice_line_ids:
            return False
        sale_line_ids = self.invoice_line_ids.mapped('sale_line_ids')
        if not sale_line_ids:
            return False
        return sale_line_ids.mapped('order_id')[0].analytic_account_id

    def _get_invoice_analytic_account(self):
        if not self.invoice_line_ids:
            return False
        analytic_account_ids = []
        for line in self.invoice_line_ids:
            if line.analytic_distribution:
                for key in line.analytic_distribution.keys():
                    analytic_account_ids.append(int(key))

        return self.env['account.analytic.account'].browse(analytic_account_ids)

    def _get_number_partner_analytic(self, partner, current_invoice, analytic_account):
        current_date = current_invoice.date
        from_date = current_date + relativedelta(month=1, day=1)
        to_date = current_date + relativedelta(years=1, month=1, day=1)
        domain = [
            ('partner_id.commercial_partner_id', 'parent_of', partner.id), ('journal_id.type', '=', 'sale'),
            ('date', '>=', from_date), ('date', '<', to_date), ('id', '!=', current_invoice.id)
        ]
        partner_invoices = self.search(domain)
        number = 1
        for invoice in partner_invoices:
            invoice_aa = invoice._get_sale_analytic_account()
            # if PI of CI doesn't contain AA then get from field 'analytic distribution'
            if not invoice_aa:
                invoice_aa = invoice._get_invoice_analytic_account()
            # if invoice_aa == analytic_account:
            if invoice_aa and invoice_aa[0].name == analytic_account.name and analytic_account.name in invoice.name:  # check AA code
                number += 1
        return "{0:02d}".format(number)

    def _compute_customer_inovoice_sequence(self):
        analytic_account = self._get_sale_analytic_account()
        if not analytic_account:
            raise UserError(_('Invoice: Missing Analytic Account value'))
        number = self._get_number_partner_analytic(self.partner_id, self, analytic_account)
        name = "{}-{}-CI".format(analytic_account.name, number)
        if self.sudo().search([('name', '=', name)]):
            largest_move = self.sudo().search([('name', 'ilike', analytic_account.name)], order='name desc', limit=1)
            number = int(largest_move.name.split('-')[-2]) + 1 if largest_move.name.split('-')[-2].isdigit() else 1
            name = "{}-{}-CI".format(analytic_account.name, "{0:02d}".format(number))
        return name
