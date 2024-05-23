# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _, fields, api


class BankBookReportCustomHandler(models.AbstractModel):
    _name = 'account.bank.book.report.handler'
    _inherit = 'account.cash.book.report.handler'
    _description = 'Bank Book Report Custom Handler'

    def _get_custom_display_config(self):
        res = super()._get_custom_display_config()
        res.update({
            'pdf_export': {
                'pdf_export_main_table_header': 'account_reports.journal_report_pdf_export_main_table_header',
                'pdf_export_filters': 'account_reports.journal_report_pdf_export_filters',
                'pdf_export_main_table_body': 'soa_finance_report.bank_report_pdf_export_main_table_body',
            },
        })
        return res

    def _get_query_sums(self, report, options):
        account_objs = self.env['account.account'].search([
            ('code', '=like', '112%'), ('account_type', '=', 'asset_cash')])
        res = super(BankBookReportCustomHandler, self)._get_query_sums(report, options ,account_ids=account_objs.ids)
        return res

    def _report_expand_unfoldable_line_general_ledger(self, line_dict_id, groupby, options, progress, offset,
                                                      xml_id=None, unfold_all_batch_data=None):
        xml_id = 'soa_finance_report.bank_book_report'
        return super()._report_expand_unfoldable_line_general_ledger(line_dict_id, groupby, options, progress, offset,
                                                      xml_id, unfold_all_batch_data)
