# -*- coding: utf-8 -*-
import copy
import os

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.soa_sale_management.report.misc import get_format_workbook
from odoo.tools import unsafe_eval


def write_with_colspan(sheet, x, y, value, colspan, style):
    if colspan == 1:
        sheet.write(y, x, value, style)
    else:
        sheet.merge_range(y, x, y, x + colspan - 1, value, style)


class SaleOrderSourcingXlsx(models.AbstractModel):
    _name = "report.soa_sale_management.sale_order_sourcing_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Sale Order Sourcing Report"

    def generate_xlsx_report(self, workbook, data, orders):
        if not orders:
            raise ValidationError(_('Sale Order Record is not found !'))
        style_fmt = get_format_workbook(workbook)

        for obj in orders:
            report_name = obj.name
            # One sheet by partner
            sheet = workbook.add_worksheet(report_name[:31])
            main_columns = self.get_main_column()
            for idx, col_val in enumerate(main_columns):
                sheet.set_column(idx, idx, col_val[0])
            self.write_report_header_to_sheet(sheet, obj)
            x_offset = 0
            y_offset = 11
            self.write_report_name_to_sheet(sheet, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset = 13
            self.write_general_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset = 20
            self.write_logicstic_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset = 29
            self.write_product_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset += len(obj.order_line) + 2  # Header and Subheader
            current_y = self.write_subtotal_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            y_offset = current_y + 1
            self.write_note_info_to_sheet(sheet, obj, x_offset, y_offset, style_fmt)
            x_offset = 0
            y_offset += 15
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
        write_with_colspan(sheet, x_offset, y_offset, 'SALE ORDER', 32, style_fmt['title_format'])

    def write_general_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        """"""
        curr_x = x_offset
        curr_y = y_offset

        # write seller info
        seller_title = 'THE SELLER:'
        write_with_colspan(sheet, curr_x, curr_y, seller_title, colspan=2, style=style_fmt['info_header_format'])
        seller_name = order.company_id.name
        seller_street, seller_street2 = order.company_id.street or '', order.company_id.street2 or ''
        new_line = '\n'
        seller_street_info = f"{seller_street} {seller_street2 and new_line or ''}{seller_street2 or ''}"

        seller_contact = order.user_id
        seller_contact_info = f"Contact person: {seller_contact and seller_contact.name or ''}\nEmail: {seller_contact and seller_contact.email or ''}\nTel: {seller_contact and seller_contact.phone or ''}"
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, seller_name, colspan=2, style=style_fmt['info_content_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, seller_street_info, colspan=2, style=style_fmt['info_content_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, seller_contact_info,
                           colspan=2, style=style_fmt['info_content_format'])

        # write buyer info
        curr_x = x_offset + 11
        curr_y = y_offset
        buyer_title = 'THE BUYER:'
        write_with_colspan(sheet, curr_x, curr_y, buyer_title, colspan=2, style=style_fmt['info_header_format'])
        buyer_name = order.partner_id.name
        buyer_street, buyer_street2 = order.partner_id.street or '', order.partner_id.street2 or ''
        buyer_street_info = f"{buyer_street} {buyer_street2 and new_line or ''}{buyer_street2 or ''}"

        buyer_contact = order.partner_id.child_ids.filtered(lambda x: x.type == 'contact')
        buyer_contact_info = f"Contact person: {buyer_contact.name or ''}\nEmail: {buyer_contact.email or ''}\nTel: {buyer_contact.phone or ''}"
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, buyer_name, colspan=2, style=style_fmt['info_content_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, buyer_street_info, colspan=2, style=style_fmt['info_content_format'])
        curr_y += 1
        write_with_colspan(sheet, curr_x, curr_y, buyer_contact_info, colspan=2, style=style_fmt['info_content_format'])

    def write_logicstic_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        """"""
        curr_x = x_offset
        curr_y = y_offset
        left_fields = [
            ('PO. No.', 'po_no'),
            ('SOA PI. No.', 'name'),
            ('DATE:', 'date_order.strftime("%m-%d-%Y")'),
            ('CBM:', 'report_cbm'),
            ('ETD:', 'etd_order.strftime("%m-%d-%Y")'),
            ('PAYMENT:', 'payment_term_id.name'),
        ]
        right_fields = [
            ('COUNTRY OF ORIGIN:', 'country_of_origin'),
            ('DELIVERY TERM:', 'delivery_term'),
            ('PORT OF LOADING:', 'port_of_loading'),
            ('PORT OF DISCHARGE:', 'port_of_discharge'),
            ('CONT. #:', 'const'),
            ('SEAL #:', 'seal'),
        ]
        for label, term in left_fields:
            write_with_colspan(sheet, curr_x, curr_y, label, colspan=1, style=style_fmt['info_content_format'])
            try:
                field_value = unsafe_eval('order.{}'.format(term)) or ''
            except:
                field_value = ''
            if type(field_value) in (float, int):
                field_value = round(field_value, 2)
            write_with_colspan(sheet, curr_x + 1, curr_y, field_value,
                               colspan=1, style=style_fmt['info_content_format'])
            curr_y += 1

        curr_y = y_offset
        curr_x = curr_x + 11
        for label, term in right_fields:
            write_with_colspan(sheet, curr_x, curr_y, label, colspan=1, style=style_fmt['info_content_format'])
            try:
                field_value = unsafe_eval('order.{}'.format(term)) or ''
            except:
                field_value = ''
            write_with_colspan(sheet, curr_x + 1, curr_y, field_value,
                               colspan=1, style=style_fmt['info_content_format'])
            curr_y += 1

    def write_product_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        """"""
        x_curr = x_offset
        y_curr = y_offset
        # Insert header table
        columns = self.get_main_column()
        sub_headers = [
            (None, 6), ('PRODUCT', 7), ('INNER BOX', 5), ('MASTER BOX', 9), ('PALLET', 5)
        ]
        for name, colspan in sub_headers:
            if name:
                write_with_colspan(sheet, x_curr, y_curr, name, colspan=colspan, style=style_fmt['sub_header_format'])
            else:
                write_with_colspan(sheet, x_curr, y_curr, '', colspan=colspan, style=style_fmt['normal_format'])
            x_curr += colspan

        x_curr = x_offset
        y_curr += 1
        for __, header_key, note in columns:
            sheet.set_row(y_curr, 30)
            header_name = header_key.split('__')[-1].upper().replace('_', ' ')
            if note:
                header_name = header_name + '\n' + note
            write_with_colspan(sheet, x_curr, y_curr, header_name, colspan=1, style=style_fmt['main_header_format'])
            write_with_colspan(sheet, x_curr, y_curr + 1, note, colspan=1, style=style_fmt['main_header_format'])
            x_curr += 1

        y_curr += 1
        for line in order.order_line.filtered(lambda l: not l.display_type):
            sheet.set_row(y_curr, 75)
            x_curr = x_offset
            values = line._prepare_data_to_xlsx_report()
            for __, header_key, note in columns:
                content = '' if values[header_key] is None else values[header_key]
                style = style_fmt['normal_format']
                if type(content) in (float, int) and header_key == 'product__total_amount':
                    content = order.currency_id.format(content)
                write_with_colspan(sheet, x_curr, y_curr, content, colspan=1, style=style)
                x_curr += 1
            if line.product_id.product_tmpl_id.image_512:
                self.write_product_image_info_to_sheet(sheet, line, x_offset + 2, y_curr, style_fmt)
            y_curr += 1

    def write_product_image_info_to_sheet(self, sheet, order_line, x_offset, y_offset, style_fmt):
        curr_x = x_offset
        curr_y = y_offset
        product_tmpl_id = order_line.product_id.product_tmpl_id
        image_attach = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', product_tmpl_id._name),
            ('res_field', '=', 'image_512'),
            ('res_id', 'in', product_tmpl_id.ids),
        ])
        fname = image_attach.store_fname
        full_path = image_attach._full_path(fname)
        options = {
            'x_scale': 0.25,
            'y_scale': 0.25,
        }
        sheet.insert_image(curr_y, curr_x, full_path, options=options)

    def write_subtotal_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        """"""
        x_curr = x_offset
        y_curr = y_offset
        SPACE_NUMBER = 10
        x_curr_start = x_curr + SPACE_NUMBER
        tax_totals = order.tax_totals
        subtotal_list = [
        ]
        for subtotal in tax_totals['subtotals']:
            subtotal_list.append((subtotal['name'], order.currency_id.format(subtotal['amount'])))
            subtotal_to_show = subtotal['name']
            for amount_by_group in tax_totals['groups_by_subtotal'][subtotal_to_show]:
                subtotal_list.append((amount_by_group['tax_group_name'], order.currency_id.format(amount_by_group['tax_group_amount'])))
        subtotal_list.append(('TOTAL', order.currency_id.format(tax_totals['amount_total'])))
        deposit_amount = order.get_amount_deposit_1st()
        subtotal_list.append(('(X)% DEPOSIT FOR ORDER CONFIRMATION', order.currency_id.format(deposit_amount)))
        subtotal_list.append(('BALANCE', order.currency_id.format(tax_totals['amount_total'] - deposit_amount)))

        for label, amount in subtotal_list:
            x_curr = x_curr_start
            colspan = 2
            write_with_colspan(sheet, x_curr, y_curr, label, colspan=colspan, style=style_fmt['subtotal_format'])
            write_with_colspan(sheet, x_curr + colspan, y_curr, amount, colspan=1,
                               style=style_fmt['float_number_title_format'])
            y_curr += 1
        return y_curr

    def write_note_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        note_list = [
            ('underline', "DOCUMENTS REQUIRED : "),
            (False, ''),
            ('underline', "Remarks: (all conditions)"),
            (False, "Date of delivery"),
            (False, "Place of delivery"),
            (False, "Inspection date:"),
            (False, "Packing instructions:"),
            (False, ''),
            ('bold', "*Mass production quality is same good quality as confirmed  sample."),
            ('bold', "* If any delay in one of the delivery should happen, 1,5% of the total order amount penalty should apply to the seller every week until delivery."),
            ('bold', "*If the Final Inspection shows differences with confirmed sample, Source Of Asia Ltd has the right to refuse the goods, unless agreement is found with seller."),
            ('bold', "*Packing dimensions, weight, and loadability are binding by this contract. No short-shipment nor overloading will be accepted, unless agreed upon, at the seller's request, and by written"),
            ('bold', "confirmation from Source Of Asia. In case of overloading, the overloaded goods will not be paid. In case of short-shipment, compensation on the LCL / added shipments will be claimed"),
        ]
        x_curr = x_offset
        y_curr = y_offset
        for prop, content in note_list:
            if prop == 'bold':
                style = style_fmt['bold_note_format']
            elif prop == 'underline':
                style = style_fmt['underline_note_format']
            else:
                style = style_fmt['note_format']
            write_with_colspan(sheet, x_curr, y_curr, content, colspan=1, style=style)
            y_curr += 1

    def write_payment_info_to_sheet(self, sheet, order, x_offset, y_offset, style_fmt):
        x_curr = x_offset
        y_curr = y_offset

        write_with_colspan(sheet, x_curr, y_curr, 'Banking information:', colspan=1, style=style_fmt['underline_note_format'])
        y_curr += 1

        info_list = list()
        info_list.append(('Beneficiary: ', order.company_id.name))
        bank_ids = order.company_id.partner_id.bank_ids
        numbers = [f'{bank.acc_number} {bank.currency_id.name and "(%s)" % bank.currency_id.name or ""}' for bank in bank_ids]
        info_list.append((order._field_titles()['account'], numbers[0]))
        if len(numbers) > 1:
            for bank_number in numbers[1:]:
                info_list.append((None, bank_number))

        info_list += [
            (order._field_titles()['bank'], bank_ids[0].bank_id.name),
            ('Bank Address:', f'{bank_ids[0].bank_id.street}')
        ]
        if bank_ids[0].bank_id.street2:
            info_list.append((None, bank_ids[0].bank_id.street2))

        info_list.append(('Swift Code: ', bank_ids[0].bank_id.bic))
        info_list += [('All banking charges are to be borne by the Buyer.', '')]

        for label, value in info_list:
            if not (label is None):
                write_with_colspan(sheet, x_curr, y_curr, label, colspan=1, style=style_fmt['bold_note_format'])
            write_with_colspan(sheet, x_curr + 1, y_curr, value, colspan=1, style=style_fmt['normal_info_format'])
            y_curr += 1
        y_curr += 1
        write_with_colspan(sheet, x_curr + 1, y_curr, "Seller's Signature", colspan=1, style=style_fmt['bold_note_format'])
        write_with_colspan(sheet, x_curr + 3, y_curr, "Buyer's Signature", colspan=2, style=style_fmt['bold_note_format'])

    def get_main_column(self):
        """"""
        # [tuple([<column_width>, label, 'uom/note'),...]
        column_list = [
            (20, 'customer_item_no', ''),
            (20, 'supplier_item_no', ''),
            (20, 'picture', ''),
            (20, 'description', ''),
            (20, 'material', ''),
            (20, 'colour', ''),
            (12, 'product__W', '(cm)'),
            (12, 'product__L', '(cm)'),
            (12, 'product__H', '(cm)'),
            (16, 'product__hs_code', ''),
            (16, 'product__quantity', ''),
            (16, 'product__unit_price', ''),
            (16, 'product__total_amount', ''),
            (12, 'pkg_inner_box__W', '(cm)'),
            (12, 'pkg_inner_box__L', '(cm)'),
            (12, 'pkg_inner_box__H', '(cm)'),
            (16, 'pkg_inner_box__qty_per_inner_box', ''),
            (22, 'pkg_inner_box__total_inner_box', ''),
            (12, 'pkg_masterbox__W', '(cm)'),
            (12, 'pkg_masterbox__L', '(cm)'),
            (12, 'pkg_masterbox__H', '(cm)'),
            (16, 'pkg_masterbox__qty_per_export', ''),
            (16, 'pkg_masterbox__total_export', ''),
            (25, 'pkg_masterbox__nw', '(kg)'),
            (25, 'pkg_masterbox__gw', '(kg)'),
            (25, 'pkg_masterbox__volume_per_export', '(cbm)'),
            (25, 'pkg_masterbox__total_volume', '(cbm)'),
            (12, 'pkg_giftbox__W', '(cm)'),
            (12, 'pkg_giftbox__L', '(cm)'),
            (12, 'pkg_giftbox__H', '(cm)'),
            (20, 'pkg_giftbox__qty_per_pallet', ''),
            (20, 'pkg_giftbox__total_pallet', ''),
        ]
        return column_list
