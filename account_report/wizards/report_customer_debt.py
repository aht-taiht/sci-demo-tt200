import base64
from io import BytesIO

import xlsxwriter

from odoo import models, fields


class AllocationDeferredExpensesReport(models.TransientModel):
    _name = "customer.debt.report"
    _description = "Customer Debt Report"

    file = fields.Binary('Click On Download Link To Download Xls File', readonly=True)
    name = fields.Char(string='File Name', size=64)

    from_date = fields.Date(string='From Date')
    to_date = fields.Date(string='To Date')

    def get_data(self):
        query = f"""
            select b.code_customer as ma_kh
            , b.name as ten_kh 
            , e.name as nhom_spdv
            , d.name as ten_spdv
            , a.booking_name as ten_booking
            , a.source_name as nguon
            , a.user_name as nhanvien_tuvan
            , f.amount_untaxed as doanhthu_truoc_chietkhau
            , (a.price_unit * a.quantity * a.discount / 100) as chietkhau
            , (a.price_unit * a.quantity) - (a.price_unit * a.quantity * a.discount / 100) as phai_thanht_toan
            , g.tong_tt as doanh_so
            , h.gtri_dalam as gtri_dalam
            , g.tong_tt - h.gtri_dalam as gtri_conlai
            from account_move_line a
            left join res_partner b on b.id =a.partner_id
            left join product_product c on c.id = a.product_id
            left join product_template d on d.id = c.product_tmpl_id
            left join product_category e on e.id = d.categ_id
            left join account_move f on f.id = a.move_id
            left join (
                    select aa.move_id, sum(bb.amount) as tong_tt from account_move_line aa
                    left join account_payment bb on bb.id = aa.payment_id
                    WHERE aa.company_id = {self.env.company.id}
                    group by aa.move_id
            ) g on g.move_id = f.id
            left join (
                    select aa.id, aa.credit as gtri_dalam from account_move_line aa
                    left join account_account bb on bb.id = aa.account_id
                    WHERE bb.code like '511%'
                    and aa.company_id = {self.env.company.id}
            ) h on h.id = a.id
            WHERE
            a.company_id  = {self.env.company.id}
            and a.date >= '{self.from_date}'
            and a.date <= '{self.to_date}'
        """
        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()
        return data

    def action_print(self):
        self.ensure_one()
        fl = BytesIO()
        wb = xlsxwriter.Workbook(fl)

        sheet1 = wb.add_worksheet('Bảng tổng hợp theo dõi công nợ khách hàng')

        company_name = wb.add_format({
            'valign': 'middle',
            'align': 'center',
            'bold': True,
            'font_name': 'Calibri',
            'font_size': 16
        })

        header_title = wb.add_format({
            'valign': 'middle',
            'align': 'center',
            'bold': True,
            'font_name': 'Calibri',
            'color': 'red',
            'font_size': 16
        })

        header_normal = wb.add_format({
            'valign': 'middle',
            'align': 'center',
            'bold': True,
            'font_name': 'Calibri'
        })

        header_table = wb.add_format({
            'valign': 'vjustify',
            'align': 'center',
            'bold': True,
            'font_name': 'Calibri'
        })

        left_bold = wb.add_format({
            'valign': 'middle',
            'align': 'left',
            'bold': True,
            'font_name': 'Calibri',
            'border': 0,
            'bg_color': '#D9D9D9'
        })

        left_normal = wb.add_format({
            'valign': 'vjustify',
            'align': 'left',
            'font_name': 'Calibri'
        })

        right_normal = wb.add_format({
            'valign': 'middle',
            'align': 'right',
            'font_name': 'Calibri'
        })

        center_normal_date = wb.add_format({
            'valign': 'middle',
            'align': 'center',
            'font_name': 'Calibri',
            'num_format': 'yyyy-mm-dd'
        })

        right_number_normal = wb.add_format({
            'valign': 'middle',
            'align': 'right',
            'font_name': 'Calibri',
            'num_format': '#,###'
        })

        center_normal = wb.add_format({
            'valign': 'middle',
            'align': 'center',
            'font_name': 'Calibri'
        })

        # sheet1.write(0, 1, str(self.env.company.name), company_name)
        sheet1.set_column(1, 1, 60)

        sheet1.merge_range('A2:L2', 'BÁO CÁO TỔNG HỢP THEO DÕI CÔNG NỢ KHÁCH HÀNG', header_title)
        sheet1.merge_range('A3:L3',
                     'Từ ngày: ' + self.from_date.strftime("%Y-%m-%d") + ' đến ngày: ' + self.to_date.strftime("%Y-%m-%d"),
                     header_normal)

        sheet1.write(4, 0, 'STT', header_table)
        sheet1.set_column(1, 1, 10)
        sheet1.write(4, 1, 'Mã khách hàng', header_table)
        sheet1.set_column(4, 2, 40)
        sheet1.write(4, 2, 'Tên khách hàng', header_table)
        sheet1.set_column(4, 3, 20)
        sheet1.write(4, 3, 'Số Booking', header_table)
        sheet1.set_column(4, 4, 20)
        sheet1.write(4, 4, 'Nhóm SPDV', header_table)
        sheet1.set_column(4, 5, 20)
        sheet1.write(4, 5, 'Tên SPDV', header_table)
        sheet1.set_column(4, 6, 20)
        sheet1.write(4, 6, 'Nguồn', header_table)
        sheet1.set_column(4, 7, 20)
        sheet1.write(4, 7, 'Nhân viên tư vấn', header_table)
        sheet1.set_column(4, 8, 15)
        sheet1.write(4, 8, 'Doanh thu trước chiết khấu', header_table)
        sheet1.set_column(4, 9, 15)
        sheet1.write(4, 9, 'Chiết khấu', header_table)
        sheet1.set_column(4, 10, 15)
        sheet1.write(4, 10, 'Phải thanh toán', header_table)
        sheet1.set_column(4, 11, 15)
        sheet1.write(4, 11, 'Doanh số', header_table)
        sheet1.set_column(4, 12, 15)
        sheet1.write(4, 12, 'Giá trị dịch vụ đã làm', header_table)
        sheet1.set_column(4, 13, 15)
        sheet1.write(4, 13, 'Giá trị dịch vụ còn được làm', header_table)

        data = self.get_data()

        def print_assets(i, lines, strat_no=0):
            for line in lines:
                i += 1
                sheet1.write(4 + i, 0, i - strat_no, center_normal)
                sheet1.write(4 + i, 1, line.get('ma_kh', ''), center_normal)
                sheet1.write(4 + i, 2, line.get('ten_kh', ''), left_normal)
                sheet1.write(4 + i, 3, line.get('nhom_spdv', ''), left_normal)
                sheet1.write(4 + i, 4, line.get('ten_booking', ''), left_normal)
                sheet1.write(4 + i, 5, line.get('nguon', ''), left_normal)
                sheet1.write(4 + i, 6, line.get('nhanvien_tuvan', ''), left_normal)
                sheet1.write(4 + i, 7, line.get('doanhthu_truoc_chietkhau', ''), right_number_normal)
                sheet1.write(4 + i, 8, line.get('chietkhau', ''), right_number_normal)
                sheet1.write(4 + i, 9, line.get('phai_thanht_toan', ''), right_number_normal)
                sheet1.write(4 + i, 10, line.get('sotien_conlai', ''), right_number_normal)
                sheet1.write(4 + i, 11, line.get('doanh_so', ''), right_number_normal)
                sheet1.write(4 + i, 11, line.get('gtri_dalam', ''), right_number_normal)
                sheet1.write(4 + i, 11, line.get('gtri_conlai', ''), right_number_normal)
            return i

        i = 1
        sheet1.set_row(4 + i, cell_format=left_bold)
        print_assets(i, data, 1)
        wb.close()
        buf = base64.b64encode(fl.getvalue())
        fl.close()

        filename = "bao_cao_tong_hop_theo_doi_cong_no_khach_hang"
        self.write({'file': buf, 'name': filename})
        filename += '%2Exlsx'
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': 'web/content/?model=' + self._name + '&id=' + str(
                self.id) + '&field=file&download=true&filename=' + filename,
        }
