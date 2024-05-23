# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import ValidationError

from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class AccountAssetSell(models.TransientModel):
    _inherit = 'account.asset.sell'

    def _get_domain_receive_company(self):
        current_company_id = self.env.company.id
        return [('id', '!=', current_company_id)]

    action = fields.Selection(selection_add=[('transfer', 'Transfer')], ondelete={'transfer': 'set default'})
    x_receive_company_id = fields.Many2one('res.company', 'Receive Company', domain=_get_domain_receive_company)

    # Confirm Transfer account asset
    def action_transfer(self):
        # checking depreciation_move
        number_move_draft = len(self.asset_id.depreciation_move_ids.filtered(lambda d:d.state == 'draft'))
        # checking transfer to same company
        if self.x_receive_company_id == self.env.company:
            raise ValidationError(_('Cannot transfer asset to same company. Please select other company!'))

        # Validate state
        if self.asset_id.state not in ['open', 'paused', 'close']:
            raise ValidationError(_('Cannot transfer asset not in state OPEN, PAUSED, CLOSE!'))

        # Create account move in transfer company
        # get asset_depreciated_value from depreciation_move_ids
        asset_depreciated_value = self.get_asset_depreciated_value()
        account_move_argvs = self.get_account_move_vals()
        account_move_id = self.env['account.move'].sudo().create(account_move_argvs)
        _logger.info(f"account_asset_custom: NEW Account move: {account_move_id.id}")

        # Create account asset in receive company
        receive_company_asset = self.with_user(SUPERUSER_ID).asset_id.copy({
            'company_id': self.x_receive_company_id.id,
            'salvage_value': self.asset_id.salvage_value + asset_depreciated_value,
            'asset_type': 'purchase',
            'original_value': self.asset_id.original_value,
            'account_asset_id': None,
            'account_depreciation_id': None,
            'account_depreciation_expense_id': None,
            'journal_id': None,
            'first_depreciation_date': datetime.today().date(),
        })
        receive_company_asset.name = self.asset_id.name
        receive_company_asset.account_asset_id = None
        receive_company_asset.method_number = number_move_draft
        _logger.info(f"account_asset_custom: NEW Asset: {receive_company_asset.id}")

        # Deactivate account asset
        # Close all depreciation_move that not posted
        for account_move in self.asset_id.depreciation_move_ids.filtered(lambda m: m.state == 'draft'):
            account_move.button_cancel()
        # Must change asset_id to close co deactivate
        self.asset_id.state = 'close'
        self.asset_id.active = False

    def get_account_move_vals(self):
        # Get journal and debit account from currency
        journal_id = self.asset_id.currency_id.x_transfer_journal_id
        debit_account_id = self.asset_id.currency_id.x_payable_account_id
        if (not journal_id or journal_id is None) or (not debit_account_id or debit_account_id is None):
            raise ValidationError(
                _('Please config Transfer Journal and Payable Account in Currency %s') % self.asset_id.currency_id.name)
        today = datetime.today().date()
        asset_depreciated_value = self.get_asset_depreciated_value()
        # TODO: not have partner_id again
        return {
            'ref': _(
                'Transfer') + f' {self.asset_id.name} - {self.asset_id.company_id.name} - {self.x_receive_company_id.name}',
            'journal_id': journal_id.id,
            'date': today,
            'invoice_date': today,
            'invoice_date_due': today,
            'company_id': self.asset_id.company_id.id,
            # 'partner_id': self.asset_id.partner_id.id,
            'currency_id': self.asset_id.currency_id.id,
            'line_ids': [
                (0, 0, self.get_account_move_line_vals(account_id=self.asset_id.account_depreciation_id.id,
                                                       credit=asset_depreciated_value,
                                                       name=_('Depreciated Value for Asset: ') + self.asset_id.name)),
                (0, 0, self.get_account_move_line_vals(account_id=self.asset_id.account_depreciation_expense_id.id,
                                                       credit=self.asset_id.value_residual,
                                                       name=_('Value Residual for Asset: ') + self.asset_id.name)),
                (0, 0, self.get_account_move_line_vals(account_id=debit_account_id.id,
                                                       debit=self.asset_id.value_residual + asset_depreciated_value,
                                                       name=_('Value Asset for: ') + self.asset_id.name))
            ]
        }

    def get_account_move_line_vals(self, account_id, credit=0, debit=0, name=''):
        return {
            'account_id': account_id,
            'credit': credit,
            'debit': debit,
            'name': name,
            'company_id': self.env.company.id,
        }

    def get_asset_depreciated_value(self):
        last_posted_move_ids = self.asset_id.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
        if not last_posted_move_ids:
            return 0
        return last_posted_move_ids.sorted(lambda x: x.date)[-1].asset_depreciated_value
