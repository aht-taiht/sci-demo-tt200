# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import api, fields, models, _

from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    viettel_branch_id = fields.Many2one("einvoice.viettel.branch",
            string="Viettel Branch", compute='_compute_viettel_branch')
    einvoice_number = fields.Char(string="E-Invoice Number", compute='_compute_einvoice_number', store=True)
    einvoice_date = fields.Date(string="E-Invoice Date", compute='_compute_einvoice_number', store=True)

    @api.depends('move_id.vat_invoice_ids')
    def _compute_einvoice_number(self):
        for line in self:
            einvoice_number = ''
            einvoice_date = False
            if line.move_id and line.move_id.vat_invoice_ids:
                for e_invoice in line.move_id.vat_invoice_ids:
                    if e_invoice.vsi_status == 'created':
                        einvoice_number = e_invoice.name
                        einvoice_date = e_invoice.date_invoice
            line.einvoice_number = einvoice_number
            line.einvoice_date = einvoice_date

    @api.depends('move_id.viettel_branch_id', 'move_id.viettel_branch_vat')
    def _compute_viettel_branch(self):
        for line in self:
            company_branch_id = False
            if line.move_id:
                if line.move_id.viettel_branch_vat:
                    company_branch_id = line.move_id.viettel_branch_vat.id
                elif line.move_id.company_branch_id:
                    company_branch_id = line.move_id.company_branch_id.id

            line.company_branch_id = company_branch_id

    def task_recompute_tax_base_amount(self, move_line_id):
        aml = self.env['account.move.line'].sudo().search([('id', '=', move_line_id)])
        aml.move_id._recompute_dynamic_lines(recompute_all_taxes=False, recompute_tax_base_amount=True)
        # for move_line in aml:
        #     base_lines = move_line.move_id.line_ids.filtered(
        #         lambda line: move_line.tax_line_id in line.tax_ids and move_line.product_id == line.product_id)
        #     move_line.tax_base_amount = abs(sum(base_lines.mapped('balance')))
