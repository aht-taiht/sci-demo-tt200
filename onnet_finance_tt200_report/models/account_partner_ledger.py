from odoo import models, _, fields

class PartnerLedgerCustomHandlerCustom(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _get_report_line_partners(self, options, partner, partner_values, level_shift=0):
        super()._get_report_line_partners(options, partner, partner_values, level_shift)
        company_currency = self.env.company.currency_id

        unfoldable = False
        column_values = []
        report = self.env['account.report'].browse(options['report_id'])
        for column in options['columns']:
            col_expr_label = column['expression_label']
            value = partner_values[column['column_group_key']].get(col_expr_label)
            unfoldable = unfoldable or (col_expr_label in ('debit', 'credit') and not company_currency.is_zero(value))
            column_values.append(report._build_column_dict(value, column, options=options))


        line_id = report._get_generic_line_id('res.partner', partner.id) if partner else report._get_generic_line_id('res.partner', None, markup='no_partner')

        code_customer = str(partner.code_customer) if partner and partner.code_customer else "Không mã"

        return {
            'id': line_id,
            'name': partner is not None and (code_customer + ' : ' + partner.name or '')[:128] or self._get_no_partner_line_label(),
            'columns': column_values,
            'level': 1 + level_shift,
            'trust': partner.trust if partner else None,
            'unfoldable': unfoldable,
            'unfolded': line_id in options['unfolded_lines'] or options['unfold_all'],
            'expand_function': '_report_expand_unfoldable_line_partner_ledger',
        }

