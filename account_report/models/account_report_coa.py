# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from copy import deepcopy

from odoo import models, api, _, fields


class AccountChartOfAccountReport(models.AbstractModel):
    _inherit = "account.coa.report"

    @api.model
    def _get_columns(self, options):
        header1 = [
            {'name': '', 'style': 'width:40%'},
            {'name': _('Initial Balance'), 'class': 'number', 'colspan': 2},
        ] + [
            {'name': period['string'], 'class': 'number', 'colspan': 2}
            for period in reversed(options['comparison'].get('periods', []))
        ] + [
            {'name': options['date']['string'], 'class': 'number', 'colspan': 2},
            {'name': _('Ending Balance'), 'class': 'number', 'colspan': 2},
        ]
        header2 = [
            {'name': '', 'style': 'width:40%'},
            {'name': _('Debit'), 'class': 'number o_account_coa_column_contrast'},
            {'name': _('Credit'), 'class': 'number o_account_coa_column_contrast'},
        ]
        if options.get('comparison') and options['comparison'].get('periods'):
            header2 += [
                {'name': _('Debit'), 'class': 'number o_account_coa_column_contrast'},
                {'name': _('Credit'), 'class': 'number o_account_coa_column_contrast'},
            ] * len(options['comparison']['periods'])
        header2 += [
            {'name': _('Debit'), 'class': 'number o_account_coa_column_contrast'},
            {'name': _('Credit'), 'class': 'number o_account_coa_column_contrast'},
            {'name': _('Debit'), 'class': 'number o_account_coa_column_contrast'},
            {'name': _('Credit'), 'class': 'number o_account_coa_column_contrast'},
        ]
        return [header1, header2]
