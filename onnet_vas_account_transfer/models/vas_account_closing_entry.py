# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class VASAccountClosingEntry(models.Model):
    _name = 'vas.account.closing.entry'
    _description = 'VAS Account Closing Entry'
    
    name = fields.Char(string='Name', required=True, default='/')
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    line_ids = fields.One2many('vas.account.closing.entry.line', 'entry_id', string='Lines')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    state = fields.Selection(selection=[('draft', 'Draft'),('confirm', 'Confirm')], default='draft', required=True)
    show_update_btn = fields.Boolean()
    account_transfer_ids = fields.Many2many('vas.account.transfer', 'vas_account_transfer_rel', 'closing_id', 'account_transfer_id', string='VAS Account Transfer')
    
    @api.onchange('date_from', 'date_to')
    def _onchange_date(self):
        self.show_update_btn = bool(self.line_ids)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(_('Date From must be less than Date To'))
        
    def _prepare_move_line(self, lines):
        vals = []
        for line in lines:
            vals += [(0,0,{
                    'name': line.name,
                    'account_id': line.account_id.id,
                    'offset_account': line.offset_account_id.code,
                    'debit': line.debit,
                    'credit': line.credit
                }),(0,0,{
                    'name': line.name,
                    'account_id': line.offset_account_id.id,
                    'offset_account': line.account_id.code,
                    'debit': line.credit,
                    'credit': line.debit
                })]
        return vals

    def validate(self):
        vals_2create = []
        for entry in self:
            vals_2create.append({
                'ref': entry.name,
                'date': fields.Date.context_today(self),
                'journal_id': entry.journal_id.id,
                'company_id': entry.company_id.id,
                'entry_transfer': True,
                'line_ids': entry._prepare_move_line(entry.line_ids),
            })
        if vals_2create:
            account_move = self.env['account.move'].create(vals_2create)
            for rec in self:
                rec.state = 'confirm'
                rec.name = rec.env['ir.sequence'].sudo().next_by_code('onnet_vas_account_transfer.vas_account_closing_entry')
            return {
                'type': 'ir.actions.act_window',
                'name': _("Journal Entries"),
                'res_model': 'account.move',
                'domain': [('id', 'in', account_move.ids)],
                'views': [(False, 'tree'), (False, 'form')],
                'target': 'current',
            }
            
    def action_update_entry_line(self):
        self.ensure_one()
        entry_vals = []
        report_lines = self.env['vas.account.transfer'].get_account_vas_trial_balance_report_lines(self.date_from, self.date_to, self.company_id.id)
        for transfer in self.account_transfer_ids:
            entry_vals += transfer.get_value_for_closing_entry(report_lines)
        if entry_vals:
            self.write({
                'line_ids': [(5, 0, 0)] + [(0,0, {
                    'name': val.get('name',''),
                    'account_id': val.get('origin_account_id', False),
                    'offset_account_id': val.get('dest_account_id', False),
                    'debit': val.get('debit',0.0),
                    'credit': val.get('credit',0.0),
                }) for val in entry_vals],
                'show_update_btn': False
            })
    
class VASAccountClosingEntryLine(models.Model):
    _name = 'vas.account.closing.entry.line'
    _description = 'VAS Account Closing Entry Line'
    _order = "ordinal_number asc, id asc"
    
    name = fields.Char(string='Description', required=True)
    ordinal_number= fields.Integer()
    entry_id = fields.Many2one('vas.account.closing.entry', string='Entry')
    account_id = fields.Many2one('account.account', string='Account')
    offset_account_id = fields.Many2one('account.account', string='Offset Account')
    debit = fields.Monetary(string='Debit', currency_field='company_currency_id')
    credit = fields.Monetary(string='Credit', currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', related='entry_id.company_id.currency_id', store=True)