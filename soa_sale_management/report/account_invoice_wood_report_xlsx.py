# -*- coding: utf-8 -*-
import copy
import os

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.soa_sale_management.report.misc import get_format_workbook, get_wood_format_workbook


def write_with_colspan(sheet, x, y, value, colspan, style):
    if colspan == 1:
        sheet.write(y, x, value, style)
    else:
        sheet.merge_range(y, x, y, x + colspan - 1, value, style)


class PurchaseOrderWoodXlsx(models.AbstractModel):
    _name = "report.soa_sale_management.account_invoice_wood_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Purchase Record Report"

    def generate_xlsx_report(self, workbook, data, orders):
        if not orders:
            raise ValidationError(_('Sale Order Record is not found !'))
        style_fmt = get_wood_format_workbook(self.env, workbook)

        for obj in orders:
            report_name = obj.name
            # One sheet by partner
            sheet = workbook.add_worksheet(report_name[:31])
            main_columns = self.get_main_columns()
            for idx, col_val in enumerate(main_columns):
                sheet.set_column(idx, idx, col_val[0])
            self.write_report_header_to_sheet(sheet, obj)
            x_offset = 0
            y_offset = 6
            self.write_report_name_to_sheet(sheet, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset = 8
            self.write_general_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset = 15
            self.write_product_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset += len(obj.invoice_line_ids)
            current_y = self.write_subtotal_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            y_offset = current_y + 3
            self.write_note_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset += 12
            self.write_payment_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)

    def write_report_header_to_sheet(self, sheet, order):
        custom_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
        options = {
            'x_offset': 0,
            'y_offset': 0,
            'x_scale': 0.5,
            'y_scale': 0.5,
        }
        sheet.insert_image(0, 0, custom_path + "/static/src/img/headers/company_%s.png" % str(order.company_id.id), options)

    def write_report_name_to_sheet(self, sheet, x_offset, y_offset, style_fmt):
        sheet.set_row(y_offset, 40)
        write_with_colspan(sheet, x_offset, y_offset, 'COMMERCIAL INVOICE', 6, style_fmt['report_title_format'])

    def write_general_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        """"""
        curr_x = x_offset
        curr_y = y_offset

        # write seller info
        seller_name = order.partner_id.name
        seller_street, seller_street2 = order.partner_id.street or '', order.partner_id.street2 or ''
        new_line = '\n'
        seller_street_info = f"{seller_street} {seller_street2 and new_line or ''}{seller_street2 or ''}"
        contact_ids = order.partner_id.child_ids.filtered(lambda x: x.type == 'contact')
        seller_contact_info = contact_ids and contact_ids[-1].name or ''
        seller_phone = contact_ids and contact_ids[-1].phone or ''

        write_with_colspan(sheet, curr_x, curr_y, 'Buyer:', colspan=1, style=style_fmt['title_info_format'])
        write_with_colspan(sheet, curr_x + 1, curr_y, seller_name, colspan=1, style=style_fmt['normal_info_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, 'Address:', colspan=1, style=style_fmt['title_info_format'])
        write_with_colspan(sheet, curr_x + 1, curr_y, seller_street_info, colspan=1, style=style_fmt['normal_info_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, 'Contact person:', colspan=1, style=style_fmt['title_info_format'])
        write_with_colspan(sheet, curr_x + 1, curr_y, seller_contact_info, colspan=1, style=style_fmt['normal_info_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, 'Telephone:', colspan=1, style=style_fmt['title_info_format'])
        write_with_colspan(sheet, curr_x + 1, curr_y, seller_phone, colspan=1, style=style_fmt['normal_info_format'])

        # write buyer info
        curr_x = x_offset + 3
        curr_y = y_offset

        sale_id = order.line_ids.sale_line_ids and order.line_ids.sale_line_ids.order_id[0] or False
        if not sale_id:
            raise UserError(_('The journal entry is not related to any sale Order'))

        write_with_colspan(sheet, curr_x, curr_y, 'Invoice No.:', colspan=1, style=style_fmt['title_info_format'])
        write_with_colspan(sheet, curr_x + 1, curr_y, order.name, colspan=2, style=style_fmt['normal_info_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, 'Invoice Date:', colspan=1, style=style_fmt['title_info_format'])
        write_with_colspan(sheet, curr_x + 1, curr_y, order.invoice_date.strftime("%m-%d-%Y"), colspan=2, style=style_fmt['normal_info_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, 'Payment Term:', colspan=1, style=style_fmt['title_info_format'])
        write_with_colspan(sheet, curr_x + 1, curr_y, order.invoice_payment_term_id.name or '', colspan=2, style=style_fmt['normal_info_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, 'Delivery Term:', colspan=1, style=style_fmt['title_info_format'])
        write_with_colspan(sheet, curr_x + 1, curr_y, sale_id and sale_id.delivery_term or '', colspan=2, style=style_fmt['normal_info_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, 'Shipment Date:', colspan=1, style=style_fmt['title_info_format'])
        edt_order = sale_id.etd_order and sale_id.etd_order.strftime("%m-%d-%Y") or ''
        write_with_colspan(sheet, curr_x + 1, curr_y, edt_order, colspan=2, style=style_fmt['normal_info_format'])

    def write_product_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        """"""
        x_curr = x_offset
        y_curr = y_offset
        # Insert header table
        columns = self.get_main_columns()

        x_curr = x_offset
        for __, header_key, note in columns:
            sheet.set_row(y_curr, 30)
            header_name = header_key.split('__')[-1].upper().replace('_', ' ')
            if note and note == 'currency':
                header_name = header_name + '\n' + f'{order.currency_id.name}'
            write_with_colspan(sheet, x_curr, y_curr, header_name, colspan=1, style=style_fmt['header_table_format'])
            x_curr += 1

        y_curr += 1
        line_count = 0
        for line in order.invoice_line_ids.filtered(lambda l: l.display_type not in ['line_section', 'line_note']):
            line_count += 1
            sheet.set_row(y_curr, 50)
            x_curr = x_offset
            values = self._get_product_data_for_wood_report(line)
            for __, header_key, note in columns:
                content = '' if values[header_key] is None else values[header_key]
                style = style_fmt['normal_format']
                if header_key == 'no.':
                    content = line_count
                elif type(content) in (float, int) and header_key == 'total_price':
                    content = order.currency_id.format(content)
                write_with_colspan(sheet, x_curr, y_curr, content, colspan=1, style=style)
                x_curr += 1
            y_curr += 1

    def write_subtotal_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        """"""
        x_curr = x_offset
        y_curr = y_offset

        y_curr += 1
        tax_totals = order.tax_totals
        total_quantity = sum(order.invoice_line_ids.mapped('quantity'))
        write_with_colspan(sheet, x_curr, y_curr, 'TOTAL  ', colspan=4, style=style_fmt['subtotal_format'])
        write_with_colspan(sheet, x_curr + 4, y_curr, total_quantity, colspan=1, style=style_fmt['float_number_subtotal_format'])
        write_with_colspan(sheet, x_curr + 5, y_curr, order.currency_id.format(tax_totals['amount_total']), colspan=1, style=style_fmt['float_number_subtotal_format'])

        sale_id = order.line_ids.sale_line_ids and order.line_ids.sale_line_ids[0].order_id or False
        if not sale_id:
            raise UserError(_('The journal entry is not related to any sale Order'))
        deposit_amount = sale_id.get_amount_deposit_1st()
        y_curr += 1
        write_with_colspan(sheet, x_curr, y_curr, 'DEPOSIT FOR ORDER CONFIRMATION  ', colspan=4, style=style_fmt['subtotal_format'])
        write_with_colspan(sheet, x_curr + 4, y_curr, '', colspan=1, style=style_fmt['subtotal_format'])
        write_with_colspan(sheet, x_curr + 5, y_curr, order.currency_id.format(deposit_amount), colspan=1, style=style_fmt['float_number_subtotal_format'])

        y_curr += 1
        write_with_colspan(sheet, x_curr, y_curr, 'BALANCE  ', colspan=4, style=style_fmt['subtotal_format'])
        write_with_colspan(sheet, x_curr + 4, y_curr, '', colspan=1, style=style_fmt['subtotal_format'])
        write_with_colspan(sheet, x_curr + 5, y_curr, order.currency_id.format(tax_totals['amount_total'] - deposit_amount), colspan=1, style=style_fmt['float_number_subtotal_format'])

        return y_curr

    def write_note_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):

        sale_id = order.line_ids.sale_line_ids and order.line_ids.sale_line_ids.order_id[0] or False
        if not sale_id:
            raise UserError(_('The journal entry is not related to any sale Order'))

        x_curr = x_offset
        y_curr = y_offset

        logistic_note = 'Prices are subject to be changed with notice according to sea freight at the shipping moment.'
        write_with_colspan(sheet, x_curr, y_curr, logistic_note, colspan=1, style=style_fmt['italic_format'])

        y_curr += 1
        info_list = [
            ('Port of Loading:', sale_id.port_of_loading or ''),
            ('Port of Discharge:', sale_id.port_of_discharge or ''),
            ('Country of Origin:', sale_id.country_of_origin or ''),
            ('Document:', 'Commercial Invoice, Packing List, Certificate of Origin, Fitosanitary or KD Certificate.')
        ]
        y_curr += 1
        for label, content in info_list:
            style_label = style_fmt['title_info_format']
            style_content = style_fmt['normal_info_format']
            write_with_colspan(sheet, x_curr, y_curr, label, colspan=1, style=style_label)
            write_with_colspan(sheet, x_curr + 1, y_curr, content, colspan=1, style=style_content)
            y_curr += 1

        y_curr += 2
        write_with_colspan(sheet, x_curr, y_curr, 'Note:', colspan=1, style=style_fmt['underline_note_format'])
        write_with_colspan(sheet, x_curr + 1, y_curr, sale_id.receiver_note or '', colspan=1, style=style_fmt['normal_info_format'])

        # y_curr += 1
        # write_with_colspan(sheet, x_curr, y_curr, 'Receiver :', colspan=1, style=style_fmt['title_info_format'])


    def write_payment_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        x_curr = x_offset
        y_curr = y_offset

        write_with_colspan(sheet, x_curr, y_curr, 'Banking information:', colspan=1, style=style_fmt['underline_note_format'])
        y_curr += 1

        info_list = list()
        info_list.append(('Beneficiary: ', order.company_id.name))
        bank_ids = order.company_id.partner_id.bank_ids
        numbers = [f'{bank.acc_number} ({bank.currency_id.name})' for bank in bank_ids]
        info_list.append(("Beneficiary's account: ", numbers[0]))
        if len(numbers) > 1:
            for bank_number in numbers[1:]:
                info_list.append((None, bank_number))

        info_list += [
            ('Beneficiary\'s bank:', bank_ids[0].bank_id.name),
            ('Bank Address:', f'{bank_ids[0].bank_id.street}')
        ]
        if bank_ids[0].bank_id.street2:
            info_list.append((None, bank_ids[0].bank_id.street2))

        info_list.append(('SWIFT Code: ', bank_ids[0].bank_id.bic))
        info_list += [('All banking charges are to be borne by the Buyer.', '')]

        for label, value in info_list:
            if not (label is None):
                write_with_colspan(sheet, x_curr, y_curr, label, colspan=1, style=style_fmt['bold_note_format'])
            write_with_colspan(sheet, x_curr + 1, y_curr, value, colspan=1, style=style_fmt['normal_info_format'])
            y_curr += 1
        y_curr += 1
        write_with_colspan(sheet, x_curr + 1, y_curr, "Seller's Signature", colspan=1, style=style_fmt['bold_note_format'])
        write_with_colspan(sheet, x_curr + 3, y_curr, "Buyer's Signature", colspan=2, style=style_fmt['bold_note_format'])

    def get_main_columns(self):
        """"""
        # [tuple([<column_width>, label, 'uom/note'),...]
        column_list = [
            (15, 'no.', ''),
            (56, 'product_name', ''),
            (10, 'unit', ''),
            (15, 'unit_price', ''),
            (17, 'quantity', ''),
            (25, 'total_price', 'currency'),
        ]
        return column_list

    def _get_product_data_for_wood_report(self, line):
        return {
            'no.': 0,
            'product_name': line.name,
            'unit': line.product_uom_id.name,
            'unit_price': line.price_unit,
            'quantity': line.quantity,
            'total_price': line.price_total
        }
