from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    balance = fields.Monetary('Số dư')
    asset_start_date = fields.Date(string='Asset Start Date', readonly=True, store=True)
    discount_cash = fields.Monetary('Discount cash')

    # @api.depends('debit','credit')
    # def get_balance_line(self):
    #     for record in self:
    #         record.balance = record.debit - record.credit
    #
    # account_rec_id = fields.Many2one('account.account', 'TK Đối ứng', compute="compute_move_id", store=True)
    # move_line_rec_id = fields.Many2one('account.move.line', string="Move line đối ứng", compute="compute_move_id",
    #                                    store=True)
    # asset_end_date = fields.Date(string='Asset End Date', compute='_get_asset_date', readonly=True, store=True)
    # asset_mrr = fields.Float(string='Monthly Recurring Revenue', compute='_get_asset_date', readonly=True,
    #                          digits="Account", store=True)
    #
    # @api.depends('move_id')
    # def compute_move_id(self):
    #
    #     for rec in self:
    #         if rec.move_id:
    #             reconcile_line = rec.move_id.line_ids.search(
    #                 [('move_id', '=', rec.move_id.id),
    #                  ('account_id', 'not in', [rec.account_id.id])], limit=1)
    #
    #             rec.account_rec_id = reconcile_line.account_id
    #             rec.move_line_rec_id = reconcile_line
    #         else:
    #             rec.account_rec_id, rec.move_line_rec_id = False, False
    #
    # @api.depends('asset_category_id', 'move_id.invoice_date')
    # def _get_asset_date(self):
    #     for record in self:
    #         record.asset_mrr = 0
    #         record.asset_start_date = False
    #         record.asset_end_date = False
    #         cat = record.asset_category_id
    #         if cat:
    #             if cat.method_number == 0 or cat.method_period == 0:
    #                 raise UserError(_(
    #                     'The number of depreciations or the period length of your asset category cannot be null.'))
    #             months = cat.method_number * cat.method_period
    #             if record.move_id.type in ['out_invoice', 'out_refund']:
    #                 record.asset_mrr = record.price_subtotal_signed / months
    #             if record.move_id.invoice_date:
    #                 start_date = datetime.strptime(
    #                     str(record.move_id.invoice_date), DF).replace(day=1)
    #                 end_date = (start_date + relativedelta(months=months,
    #                                                        days=-1))
    #                 record.asset_start_date = start_date.strftime(DF)
    #                 record.asset_end_date = end_date.strftime(DF)
    #
    # def asset_create(self):
    #     for record in self:
    #         if record.asset_category_id:
    #             vals = {
    #                 'name': record.name,
    #                 'code': record.move_id.name or False,
    #                 'category_id': record.asset_category_id.id,
    #                 'value': record.price_subtotal,
    #                 'partner_id': record.move_id.partner_id.id,
    #                 'company_id': record.move_id.company_id.id,
    #                 'currency_id': record.move_id.company_currency_id.id,
    #                 'date': record.move_id.invoice_date,
    #                 'invoice_id': record.move_id.id,
    #             }
    #             changed_vals = record.env[
    #                 'account.asset.asset'].onchange_category_id_values(
    #                 vals['category_id'])
    #             vals.update(changed_vals['value'])
    #             asset = record.env['account.asset.asset'].create(vals)
    #             if record.asset_category_id.open_asset:
    #                 asset.validate()
    #     return True
    #
    # @api.onchange('asset_category_id')
    # def onchange_asset_category_id(self):
    #     if self.move_id.type == 'out_invoice' and self.asset_category_id:
    #         self.account_id = self.asset_category_id.account_asset_id.id
    #     elif self.move_id.type == 'in_invoice' and self.asset_category_id:
    #         self.account_id = self.asset_category_id.account_asset_id.id
    #
    # @api.onchange('product_uom_id')
    # def _onchange_uom_id(self):
    #     result = super(AccountInvoiceLine, self)._onchange_uom_id()
    #     self.onchange_asset_category_id()
    #     return result
    #
    # @api.onchange('product_id')
    # def _onchange_product_id(self):
    #     vals = super(AccountInvoiceLine, self)._onchange_product_id()
    #     if self.product_id:
    #         if self.move_id.type == 'out_invoice':
    #             self.asset_category_id = self.product_id.product_tmpl_id.deferred_revenue_category_id
    #         elif self.move_id.type == 'in_invoice':
    #             self.asset_category_id = self.product_id.product_tmpl_id.asset_category_id
    #     return vals
    #
    # def _set_additional_fields(self, invoice):
    #     if not self.asset_category_id:
    #         if invoice.type == 'out_invoice':
    #             self.asset_category_id = self.product_id.product_tmpl_id.deferred_revenue_category_id.id
    #         elif invoice.type == 'in_invoice':
    #             self.asset_category_id = self.product_id.product_tmpl_id.asset_category_id.id
    #         self.onchange_asset_category_id()
    #     super(AccountInvoiceLine, self)._set_additional_fields(invoice)
    #
    # def get_invoice_line_account(self, type, product, fpos, company):
    #     return product.asset_category_id.account_asset_id or super(
    #         AccountInvoiceLine, self).get_invoice_line_account(type, product,
    #                                                            fpos, company)