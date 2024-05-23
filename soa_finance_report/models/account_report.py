# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountReport(models.Model):
    _inherit = 'account.report'

    soa_structure = fields.Boolean('SOA Structure')
    financial_report_currency = fields.Many2one('res.currency', string='Financial Report Currency')

    @api.constrains('soa_structure')
    def _constrains_unique_soa_record(self):
        if len(self.with_context(active_test=False).search([('soa_structure', '=', True)])) > 1:
            raise UserError(_('Soa Structure Report is already existed !'))


class AccountReportLine(models.Model):
    _inherit = 'account.report.line'

    reallocation_compute = fields.Boolean('Compute Reallocation?')
    compute_after = fields.Boolean('Compute After?')
    soa_structure = fields.Boolean(related='report_id.soa_structure')

    @api.constrains('reallocation_compute', 'expression_ids')
    def _check_unique_expression_for_reallocation(self):
        for line in self:
            if line.reallocation_compute and len(line.expression_ids) != 1:
                raise UserError(_('Must have only one expression line for reallocation report line: %s !', line.name))
