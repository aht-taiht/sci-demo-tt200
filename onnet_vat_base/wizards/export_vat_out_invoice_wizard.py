# -*- coding: utf-8 -*-
import io
import keyword
import re
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import expr_eval


class ExportVATOutInvoiceWizard(models.TransientModel):
    _name = 'export.vat.out.invoice.wizard'
    _inherit = 'export.vat.invoice.common'
    _description = 'Export Vat Out Invoice Wizard'

    def _get_report_name(self):
        return _('Vat Out Invoice')

    def get_lines(self, tax):
        fields = ['invoice_id', 'price_subtotal', 'vat_amount', 'invoice_line_tax_ids']
        domain = [
            ('invoice_id.date', '>=', self.date_from),
            ('invoice_id.date', '<=', self.date_to),
            ('invoice_id.type', 'in', ('out_invoice', 'out_refund')),
            ('invoice_id.company_id', '=', self.company_id.id),
            # ('invoice_id.vsi_status', 'in', ('creating', 'created'))
        ]
        if tax:
            tax_2 = tax + ' VAT'
            tax_3 = tax + ' Vat'
            domain += [('invoice_line_tax_ids.name', 'in', (tax, tax_2, tax_3))]
        else:
            domain += [('invoice_line_tax_ids', '=', False)]

        in_lines = self.env['account.vat.invoice.line'].search_read(domain=domain, fields=fields)
        for line in in_lines:
            invoice_id = self.env['account.vat.invoice'].browse(line['invoice_id'][0])
            line['invoice_id'] = invoice_id
        return in_lines

    def _inject_report_into_xlsx_sheet(self, workbook, sheet):
        def write_cell(sheet, row, col, value, style):
            sheet.write(row, col, value, style)

        def write_with_merge(shee, first_row, first_col, last_row, last_col, value, style):
            sheet.merge_range(first_row, first_col, last_row, last_col, value, style)

        # Define cell style
        default_format = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12})
        form_format = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 12, 'align': "center", 'text_wrap': True})
        title_format = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 16, 'align': "center", 'bold': True})

        header_format = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 12, 'align': "center", 'bold': True, 'border': 1, 'fg_color': "#87cefa"})

        cell_title_format = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 12, 'bold': True, 'border': 1, 'num_format': '#,###'})
        cell_val_format = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 11, 'border': 1, 'num_format': '#,###'})

        sign_bold_format = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 12, 'bold': True, 'align': "center"})
        sign_format = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'align': "center"})

        # Set column width
        sheet.set_column('A:A', 15)
        sheet.set_column('B:C', 20)
        sheet.set_column('D:D', 35)
        sheet.set_column('E:G', 30)
        sheet.set_column('H:H', 15)

        # Set row height
        sheet.set_default_row(20)
        sheet.set_row(0, 25)
        sheet.set_row(1, 25)
        sheet.set_row(2, 25)
        sheet.set_row(3, 20)

        # Company
        company_name = _("Công ty: {}").format(self.company_id.name)
        write_with_merge(sheet, 0, 0, 0, 2, company_name, default_format)

        # Address
        address = _("Địa chỉ: {}").format(self.company_id.street)
        write_with_merge(sheet, 1, 0, 1, 4, address, default_format)

        # Form Name
        template_name = "Mẫu số 01: 01 -1/GTGT(Ban hành kèm theo thông tư số 119/2014/TT-BTC ngày 25/8/2014 của Bộ tài chính)"
        write_with_merge(sheet, 0, 6, 1, 7, template_name, form_format)

        # Report title
        report_title = "BẢNG KÊ HÓA ĐƠN, CHỨNG TỪ CỦA HÀNG HÓA, DỊCH VỤ BÁN RA"
        write_with_merge(sheet, 2, 3, 2, 5, report_title, title_format)

        # Period
        period_str = _("Từ ngày: {} - Đến ngày: {}").format(
            self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y'))
        write_with_merge(sheet, 3, 3, 3, 5, period_str, form_format)

        # Currency
        currency_str = _("Tiền tệ: ")
        write_cell(sheet, 4, 6, currency_str, default_format)
        currency_val = self.company_id.currency_id.name
        write_cell(sheet, 4, 7, currency_val, default_format)

        # Table Header
        header_str = _("STT")
        write_with_merge(sheet, 5, 0, 6, 0, header_str, header_format)
        header_str = _("Hóa đơn, chứng từ")
        write_with_merge(sheet, 5, 1, 5, 2, header_str, header_format)
        header_str = _("Số hóa đơn")
        write_cell(sheet, 6, 1, header_str, header_format)
        header_str = _("Ngày, tháng ghi sổ")
        write_cell(sheet, 6, 2, header_str, header_format)
        header_str = _("Khách hàng")
        write_with_merge(sheet, 5, 3, 6, 3, header_str, header_format)
        header_str = _("Mã số Thuế")
        write_with_merge(sheet, 5, 4, 6, 4, header_str, header_format)
        header_str = _("Giá trị trước thuế")
        write_with_merge(sheet, 5, 5, 6, 5, header_str, header_format)
        header_str = _("Thuế")
        write_with_merge(sheet, 5, 6, 6, 6, header_str, header_format)
        header_str = _("Ghi chú")
        write_with_merge(sheet, 5, 7, 6, 7, header_str, header_format)
        header_str = ("1", "2", "3", "4", "5", "6", "7", "8")
        sheet.write_row(7, 0, header_str, header_format)

        # Writing cell
        row = 7
        col = 0
        all_excl_tax_total = 0
        all_tax_total = 0

        row += 1
        title_cell_str = _("1. Hàng hóa & Dịch vụ chịu thuế GTGT 10%")
        write_with_merge(sheet, row, col, row, col + 7, title_cell_str, cell_title_format)

        lines = self.get_lines(tax='10%')
        # cell val
        for i, line in enumerate(lines, 1):
            row += 1
            write_cell(sheet, row, 0, i, cell_val_format)
            write_cell(sheet, row, 1, line['invoice_id'].name or '', cell_val_format)
            write_cell(sheet, row, 2, line['invoice_id'].date_invoice.strftime('%d/%m/%Y'), cell_val_format)
            write_cell(sheet, row, 3, line['invoice_id'].partner_id.name or '', cell_val_format)
            write_cell(sheet, row, 4, line['invoice_id'].partner_id.vat or '', cell_val_format)
            write_cell(sheet, row, 5, line['price_subtotal'], cell_val_format)
            write_cell(sheet, row, 6, line['vat_amount'], cell_val_format)
            write_cell(sheet, row, 7, '', cell_val_format)
        excl_tax_total = sum([line['price_subtotal'] for line in lines])
        tax_total = sum([line['vat_amount'] for line in lines])

        all_excl_tax_total += excl_tax_total
        all_tax_total += tax_total

        row += 1
        title_cell_str = _("Tổng")
        write_with_merge(sheet, row, col, row, col + 4, title_cell_str, cell_title_format)
        write_cell(sheet, row, 5, excl_tax_total, cell_title_format)
        write_cell(sheet, row, 6, tax_total, cell_title_format)
        write_cell(sheet, row, 7, '', cell_title_format)

        row += 1
        title_cell_str = _("2. Hàng hóa & Dịch vụ chịu thuế GTGT 8%")
        write_with_merge(sheet, row, col, row, col + 7, title_cell_str, cell_title_format)

        lines = self.get_lines(tax='8%')
        # cell val
        for i, line in enumerate(lines, 1):
            row += 1
            write_cell(sheet, row, 0, i, cell_val_format)
            write_cell(sheet, row, 1, line['invoice_id'].name or '', cell_val_format)
            write_cell(sheet, row, 2, line['invoice_id'].date_invoice.strftime('%d/%m/%Y'), cell_val_format)
            write_cell(sheet, row, 3, line['invoice_id'].partner_id.name or '', cell_val_format)
            write_cell(sheet, row, 4, line['invoice_id'].partner_id.vat or '', cell_val_format)
            write_cell(sheet, row, 5, line['price_subtotal'], cell_val_format)
            write_cell(sheet, row, 6, line['vat_amount'], cell_val_format)
            write_cell(sheet, row, 7, '', cell_val_format)
        excl_tax_total = sum([line['price_subtotal'] for line in lines])
        tax_total = sum([line['vat_amount'] for line in lines])

        all_excl_tax_total += excl_tax_total
        all_tax_total += tax_total

        row += 1
        title_cell_str = _("Tổng")
        write_with_merge(sheet, row, col, row, col + 4, title_cell_str, cell_title_format)
        write_cell(sheet, row, 5, excl_tax_total, cell_title_format)
        write_cell(sheet, row, 6, tax_total, cell_title_format)
        write_cell(sheet, row, 7, '', cell_title_format)

        row += 1
        title_cell_str = _("3. Hàng hóa & Dịch vụ chịu thuế GTGT 5%")
        write_with_merge(sheet, row, col, row, col + 7, title_cell_str, cell_title_format)

        lines = self.get_lines(tax='5%')
        # cell val
        for i, line in enumerate(lines, 1):
            row += 1
            write_cell(sheet, row, 0, i, cell_val_format)
            write_cell(sheet, row, 1, line['invoice_id'].name or '', cell_val_format)
            write_cell(sheet, row, 2, line['invoice_id'].date_invoice.strftime('%d/%m/%Y'), cell_val_format)
            write_cell(sheet, row, 3, line['invoice_id'].partner_id.name or '', cell_val_format)
            write_cell(sheet, row, 4, line['invoice_id'].partner_id.vat or '', cell_val_format)
            write_cell(sheet, row, 5, line['price_subtotal'], cell_val_format)
            write_cell(sheet, row, 6, line['vat_amount'], cell_val_format)
            write_cell(sheet, row, 7, '', cell_val_format)
        excl_tax_total = sum([line['price_subtotal'] for line in lines])
        tax_total = sum([line['vat_amount'] for line in lines])

        all_excl_tax_total += excl_tax_total
        all_tax_total += tax_total

        row += 1
        title_cell_str = _("Tổng")
        write_with_merge(sheet, row, col, row, col + 4, title_cell_str, cell_title_format)
        write_cell(sheet, row, 5, excl_tax_total, cell_title_format)
        write_cell(sheet, row, 6, tax_total, cell_title_format)
        write_cell(sheet, row, 7, '', cell_title_format)

        row += 1
        title_cell_str = _("4. Hàng hóa & Dịch vụ chịu thuế GTGT 0%")
        write_with_merge(sheet, row, col, row, col + 7, title_cell_str, cell_title_format)

        lines = self.get_lines(tax='0%')
        # cell val
        for i, line in enumerate(lines, 1):
            row += 1
            write_cell(sheet, row, 0, i, cell_val_format)
            write_cell(sheet, row, 1, line['invoice_id'].name or '', cell_val_format)
            write_cell(sheet, row, 2, line['invoice_id'].date_invoice.strftime('%d/%m/%Y'), cell_val_format)
            write_cell(sheet, row, 3, line['invoice_id'].partner_id.name or '', cell_val_format)
            write_cell(sheet, row, 4, line['invoice_id'].partner_id.vat or '', cell_val_format)
            write_cell(sheet, row, 5, line['price_subtotal'], cell_val_format)
            write_cell(sheet, row, 6, line['vat_amount'], cell_val_format)
            write_cell(sheet, row, 7, '', cell_val_format)
        excl_tax_total = sum([line['price_subtotal'] for line in lines])
        tax_total = sum([line['vat_amount'] for line in lines])

        all_excl_tax_total += excl_tax_total
        all_tax_total += tax_total

        row += 1
        title_cell_str = _("Tổng")
        write_with_merge(sheet, row, col, row, col + 4, title_cell_str, cell_title_format)
        write_cell(sheet, row, 5, excl_tax_total, cell_title_format)
        write_cell(sheet, row, 6, tax_total, cell_title_format)
        write_cell(sheet, row, 7, '', cell_title_format)

        row += 1
        title_cell_str = _("5. Hàng hóa, dịch vụ không chịu thuế GTGT")
        write_with_merge(sheet, row, col, row, col + 7, title_cell_str, cell_title_format)

        lines = self.get_lines(tax=False)
        # cell val
        for i, line in enumerate(lines, 1):
            row += 1
            write_cell(sheet, row, 0, i, cell_val_format)
            write_cell(sheet, row, 1, line['invoice_id'].name or '', cell_val_format)
            write_cell(sheet, row, 2, line['invoice_id'].date_invoice.strftime('%d/%m/%Y'), cell_val_format)
            write_cell(sheet, row, 3, line['invoice_id'].partner_id.name or '', cell_val_format)
            write_cell(sheet, row, 4, line['invoice_id'].partner_id.vat or '', cell_val_format)
            write_cell(sheet, row, 5, line['price_subtotal'], cell_val_format)
            write_cell(sheet, row, 6, line['vat_amount'], cell_val_format)
            write_cell(sheet, row, 7, '', cell_val_format)
        excl_tax_total = sum([line['price_subtotal'] for line in lines])
        tax_total = sum([line['vat_amount'] for line in lines])

        all_excl_tax_total += excl_tax_total
        all_tax_total += tax_total

        row += 1
        title_cell_str = _("Tổng")
        write_with_merge(sheet, row, col, row, col + 4, title_cell_str, cell_title_format)
        write_cell(sheet, row, 5, excl_tax_total, cell_title_format)
        write_cell(sheet, row, 6, tax_total, cell_title_format)
        write_cell(sheet, row, 7, '', cell_title_format)

        # Total
        row += 1
        row += 1
        title_cell_str = _("Tổng doanh thu hàng hóa, dịch vụ bán ra chịu thuế GTGT")
        write_with_merge(sheet, row, 0, row, 2, title_cell_str, cell_title_format)
        write_with_merge(sheet, row, 3, row, 4, all_excl_tax_total, cell_title_format)
        row += 1
        title_cell_str = _("Tổng số thuế GTGT của hàng hóa, dịch vụ bán ra")
        write_with_merge(sheet, row, 0, row, 2, title_cell_str, cell_title_format)
        write_with_merge(sheet, row, 3, row, 4, all_tax_total, cell_title_format)

        # Signature
        row += 1
        row += 1
        sign_str = _("Tháng ..... Ngày ..... Năm .....")
        write_with_merge(sheet, row, 5, row, 6, sign_str, sign_format)
        row += 1
        sign_str = _("Người ghi sổ")
        write_with_merge(sheet, row, 0, row, 1, sign_str, sign_bold_format)
        sign_str = _("Kế toán trưởng")
        write_with_merge(sheet, row, 3, row, 4, sign_str, sign_bold_format)
        sign_str = _("Giám đốc")
        write_with_merge(sheet, row, 5, row, 6, sign_str, sign_bold_format)
        row += 1
        sign_str = _("(Chữ ký, Họ và Tên)")
        write_with_merge(sheet, row, 0, row, 1, sign_str, sign_format)
        sign_str = _("(Chữ ký, Họ và Tên)")
        write_with_merge(sheet, row, 3, row, 4, sign_str, sign_format)
        sign_str = _("(Chữ ký, Họ và Tên, Dấu chức danh)")
        write_with_merge(sheet, row, 5, row, 6, sign_str, sign_format)
