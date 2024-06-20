# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VASAccountTransferWizard(models.TransientModel):
    _name = 'vas.account.transfer.wizard'
    _description = 'VAS Account Transfer Wizard'
    
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True, default=fields.Date.today)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    
    # TODO: check date to must be greater than date from
    
    def create_vas_account_transfer(self):
        ctx = dict(self.env.context)
        if ctx.get('active_model', '') != 'vas.account.transfer':
            return True
        VASAccountTransENV = self.env['vas.account.transfer']
        acc_trans_conf = VASAccountTransENV.search([('state', '=', 'active'),('company_id', '=', self.company_id.id)])
        if ctx.get('active_ids', []):
            acc_trans_conf = self.env['vas.account.transfer'].search([('id','in',ctx.get('active_ids',[])),('company_id', '=', self.company_id.id)])
        if acc_trans_conf:
            return acc_trans_conf.action_create_transfer_account(self.from_date, self.to_date, company_id=self.company_id.id, journal_id=self.journal_id.id)
        return True
    
    @api.onchange('from_date', 'to_date')
    def _onchange_date(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValidationError(_('Date From must be less than Date To'))
        