# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VASAccountTransfer(models.Model):
    _name = 'vas.account.transfer'
    _description = 'VAS Account Transfer'
    _order="ordinal_number asc"

    name = fields.Char()
    ordinal_number = fields.Integer(required=True)
    origin_account_group = fields.Many2one('account.group')
    origin_account_id = fields.Many2one('account.account', domain="[('group_id', '=', origin_account_group)]")
    dest_account_id = fields.Many2one('account.account', string='Destination Account', required=True)
    state = fields.Selection(selection=[('active', 'Active'),('inactive','Inactive')], default='active', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    
    @api.constrains('origin_account_group', 'origin_account_id')
    def _check_deferred_dates(self):
        for rec in self:
            if not rec.origin_account_group and not rec.origin_account_id:
                raise UserError(_("You cannot create an account transfer without an origin account!"))
        
    def _get_ordinal_number(self, origin_account_id, dest_account_id):
        acc_transfer = self.env['vas.account.transfer']
        if origin_account_id and dest_account_id:
            acc_transfer = self.env['vas.account.transfer'].search([
                ('origin_account_id', '=', origin_account_id),
                ('dest_account_id', '=', dest_account_id)
            ], limit=1)
        return acc_transfer and acc_transfer.ordinal_number or 0             
    
    def action_transfer_account(self):
        return {
            "name": _("Account Transfer"),
            "type": "ir.actions.act_window",
            "res_model": "vas.account.transfer.wizard",
            "target": "new",
            "views": [[False, "form"]],
            "context": {"is_modal": True, 'active_model': 'vas.account.transfer', 'active_ids': self.ids},
        }
    
    def get_account_vas_trial_balance_report_lines(self, date_from, date_to, company_id):
        # Get trial_balance_report
        account_report_id = self.env.ref('onnet_vas_trial_balance_report.vas_trial_balance_report')
        # get  report_line of trial_balance_report
        report_lines = account_report_id.get_report_information(
            self.get_option_for_account_report(account_report_id, date_from, date_to, company_id))['lines']
        return report_lines
    
    def get_option_for_account_report(self, instance, date_from, date_to, company_id):
        '''
            Set up condition for query line of report
            instance: report [object]
        '''
        options = instance.get_options()
        # replace companies/date key
        options['date']['date_from'] = date_from
        options['date']['date_to'] = date_to
        if company_id:
            company_options = self.env['res.company'].browse(company_id)
            options['companies'] = [
                {
                    'currency_id': company_options.currency_id.id,
                    'id': company_options.id,
                    'name': company_options.name
                }
            ]
        return options
    
    def _parse_id_val(self, id_val):
        return [
            (model or None, int(value) if model and value else (value or None))
            for model, value in (key.split('~') for key in id_val.split('|'))
        ]
    
    def _prepare_value_for_closing_entry(self, account_vals, col_val, origin_account_id):
        for col in filter(lambda x: 'end_balance' in x['column_group_key'], col_val):
            need_add_new = True
            for account in account_vals:
                id_val_key = self._parse_id_val(account['id'])
                if self.id == id_val_key[0][1] and origin_account_id == id_val_key[1][1]:
                    account.update({
                        col['expression_label']: account[col['expression_label']] + col['no_format']\
                            if col['expression_label'] in account else col['no_format'],
                    })
                    need_add_new = False
            if need_add_new:
                account_vals.append({
                    'id': '%s~%s|account.account~%s' %(self._name, self.id, origin_account_id),
                    col['expression_label']: col['no_format'],
                    'origin_account_id': origin_account_id,
                    'dest_account_id': self.dest_account_id.id,
                    'name': self.name
                })
        return account_vals
    
    def get_value_for_closing_entry(self, report_lines):
        self.ensure_one()
        # self is transfer line config 
        col_val = []
        account_vals = []
        for line in report_lines:
            line_id = self.env.ref('onnet_vas_trial_balance_report.vas_trial_balance_report')._parse_line_id(line['id'])
            if self.origin_account_id:
                for id_tuple in line_id:
                    if id_tuple[1] == 'account.account' and id_tuple[2] == self.origin_account_id.id:
                        account_vals = self._prepare_value_for_closing_entry(account_vals, line['columns'], self.origin_account_id.id)
            elif not self.origin_account_id and self.origin_account_group:
                for account in self.origin_account_group.account_ids:
                    for id_tuple in line_id:
                        if id_tuple[1] == 'account.account' and id_tuple[2] == account.id:
                            account_vals = self._prepare_value_for_closing_entry(account_vals, line['columns'], account.id)
        return account_vals
        
    def action_create_transfer_account(self, date_from, date_to, company_id=None, journal_id=None):
        account_vals = []
        report_lines = self.get_account_vas_trial_balance_report_lines(date_from, date_to, company_id and company_id or self.env.company.id)
        for transfer in self:
            account_vals += transfer.get_value_for_closing_entry(report_lines)
        if account_vals:
            closing_entry = self.env['vas.account.closing.entry'].create({
                'date_from': date_from,
                'date_to': date_to,
                'journal_id': journal_id,
                'company_id': company_id,
                'account_transfer_ids': [(4, trans.id, False) for trans in self],
                'line_ids': [(0,0, {
                    'name': val.get('name',''),
                    'ordinal_number': self._get_ordinal_number(val.get('origin_account_id', False), val.get('dest_account_id', False)),
                    'account_id': val.get('origin_account_id', False),
                    'offset_account_id': val.get('dest_account_id', False),
                    'debit': val.get('debit',0.0),
                    'credit': val.get('credit',0.0),
                }) for val in account_vals]
            })
            return {
                'type': 'ir.actions.act_window',
                'name': _("Closing Entry"),
                'context': {'create': False},
                'view_mode': 'form',
                'res_model': 'vas.account.closing.entry',
                'res_id': closing_entry.id,
                'view_id': self.env.ref('onnet_vas_account_transfer.vas_account_closing_entry_form').id,
                'target': 'current',
            }
        