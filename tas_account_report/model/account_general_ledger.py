from odoo import models, fields, api, _
from odoo.tools.misc import format_date, DEFAULT_SERVER_DATE_FORMAT
from datetime import timedelta


class AccountGeneralLedgerReport(models.AbstractModel):
    _inherit = "account.general.ledger"


    @api.model
    def _get_options_domain(self, options):
        # OVERRIDE
        domain = super(AccountGeneralLedgerReport, self)._get_options_domain(options)
        have_or = False

        # Filter accounts based on the search bar.
        if options.get('offset_accounts'):
            for rec in options.get('offset_accounts', []):
                if rec['selected']:
                    if have_or:
                        domain.insert(len(domain)-1, '|')
                    domain.append(('offset_account_ids', '=', rec['id']))
                    have_or = True
        return domain
