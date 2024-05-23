# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    x_code = fields.Char(string='Mã tài sản')
    x_employee_id = fields.Many2one('hr.employee', string='Nhân viên')
    x_specification = fields.Text(string='Thông số của máy')
    x_info_invoice = fields.Char(string='Thông tin hóa đơn')
    x_date_invoice = fields.Date(string='Ngày hóa đơn')
    company_name = fields.Char(string='Công ty', related='company_id.name')
    x_qty = fields.Float(string='Qty')
    x_uom_id = fields.Many2one('uom.uom', string='Uom')


