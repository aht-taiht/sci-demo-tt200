
import lxml.html
from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_paid_amount(self):
        result = 0.0
        if self.state == 'posted' and self.is_invoice(include_receipts=True):
            reconciled_partials = self.sudo()._get_all_reconciled_invoice_partials()
            for reconciled_partial in reconciled_partials:
                if not reconciled_partial['is_exchange']:
                    result += reconciled_partial['currency']._convert(
                        reconciled_partial['amount'], self.currency_id, self.company_id, self.date
                    )
        return result

    def has_narration_content(self):
        document = lxml.html.document_fromstring(self.narration or '<div></div>')
        content = document.text_content() or ''
        return bool(content.encode("ascii", "ignore").decode().strip())

    def _field_titles(self):
        return {
            'bank': 'Bank: ' if 'source' in self.company_id.name.lower() else 'Beneficiary’s bank: ',
            'account': 'Account Number: ' if 'source' in self.company_id.name.lower() else 'Beneficiary’s account:'
        }