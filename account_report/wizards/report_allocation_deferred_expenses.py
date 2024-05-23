import base64
from io import BytesIO

import xlsxwriter

from odoo import models, fields


class AllocationDeferredExpensesReport(models.TransientModel):
    _name = "allocation.deferred.expenses.report"
    _description = "Allocation Deferred Expenses Report"

    file = fields.Binary('Click On Download Link To Download Xls File', readonly=True)
    name = fields.Char(string='File Name', size=64)

    date = fields.Date(string='Date')
    account = fields.Many2one('account.account', string='Account')

    def get_data(self):
        query = f"""
            select 
            a.x_code as machiphi
            , a.name as tenchiphi
            , a.acquisition_date as ngayghinhan
            , a.method_number as soky_pbo
            , a.method_number - (select count(*) from account_move where date <= '{self.date}' and state = 'posted') as soky_conlai
            , a.original_value as so_tien
            , expense_board.amount_total as sotien_pbo_hangky
            , expense_board.asset_depreciated_value as pbo_trongky
            , expense_board.asset_depreciated_value as luyke_pbo
            , expense_board.asset_remaining_value as sotien_conlai
            , b.code as tk_cho_pb
            from account_asset a
            left join (select amount_total, asset_depreciated_value, asset_id, asset_remaining_value
                            from account_move
                            where date = (select max(date) from account_move WHERE date <= '{self.date}')
                            and company_id = {self.env.company.id}
                            and state = 'posted' limit 1) expense_board on expense_board.asset_id = a.id
            left join account_account b on b.id = a.account_depreciation_id
            where a.company_id = {self.env.company.id}
        """
        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()
        return data

    def action_print(self):
        self.ensure_one()
        fl = BytesIO()
        wb = xlsxwriter.Workbook(fl)

        sheet1 = wb.add_worksheet('Báo cáo tình hình phân bổ chi phí trả trước')

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

        sheet1.write(0, 1, str(self.env.company.name), company_name)
        sheet1.set_column(1, 1, 60)

        sheet1.merge_range('A2:L2', 'BÁO CÁO TÌNH HÌNH PHÂN BỔ CHI PHÍ TRẢ TRƯỚC', header_title)
        sheet1.merge_range('A3:L3',
                     'Ngày: ' + self.date.strftime("%Y-%m-%d"),
                     header_normal)

        sheet1.write(4, 0, 'STT', header_table)
        sheet1.set_column(1, 1, 10)
        sheet1.write(4, 1, 'Mã chi phí trả trước', header_table)
        sheet1.set_column(4, 2, 40)
        sheet1.write(4, 2, 'Tên chi phí trả trước', header_table)
        sheet1.set_column(4, 3, 15)
        sheet1.write(4, 3, 'Ngày ghi nhận', header_table)
        sheet1.write(4, 4, 'Số kỳ phân bổ', header_table)
        sheet1.write(4, 5, 'Số kỳ phân bổ còn lại', header_table)
        sheet1.set_column(4, 6, 10)
        sheet1.write(4, 6, 'Số tiền', header_table)
        sheet1.set_column(4, 7, 10)
        sheet1.write(4, 7, 'Số tiền phân bổ hàng kỳ', header_table)
        sheet1.set_column(4, 8, 10)
        sheet1.write(4, 8, 'Phân bổ trong kỳ', header_table)
        sheet1.set_column(4, 9, 10)
        sheet1.write(4, 9, 'Lũy kế đã phân bổ ', header_table)
        sheet1.set_column(4, 10, 10)
        sheet1.write(4, 10, 'Số tiền còn lại', header_table)
        sheet1.write(4, 11, 'Tài khoản chờ phân bổ', header_table)

        data = self.get_data()

        def print_assets(i, lines, strat_no=0):
            for line in lines:
                i += 1
                sheet1.write(4 + i, 0, i - strat_no, center_normal)
                sheet1.write(4 + i, 1, line.get('machiphi', ''), center_normal)
                sheet1.write(4 + i, 2, line.get('tenchiphi', ''), left_normal)
                sheet1.write(4 + i, 3, line.get('ngayghinhan', ''), center_normal_date)
                sheet1.write(4 + i, 4, line.get('soky_pbo', ''), center_normal)
                sheet1.write(4 + i, 5, line.get('soky_conlai', ''), center_normal)
                sheet1.write(4 + i, 6, line.get('so_tien', ''), right_number_normal)
                sheet1.write(4 + i, 7, line.get('sotien_pbo_hangky', ''), right_number_normal)
                sheet1.write(4 + i, 8, line.get('pbo_trongky', ''), right_number_normal)
                sheet1.write(4 + i, 9, line.get('luyke_pbo', ''), right_number_normal)
                sheet1.write(4 + i, 10, line.get('sotien_conlai', ''), right_number_normal)
                sheet1.write(4 + i, 11, line.get('tk_cho_pb', ''), center_normal)
            return i

        i = 1
        sheet1.set_row(4 + i, cell_format=left_bold)
        print_assets(i, data, 1)
        wb.close()
        buf = base64.b64encode(fl.getvalue())
        fl.close()

        filename = "bao_cao_tinh_hinh_phan_bo_chi_phi_tra_truoc"
        self.write({'file': buf, 'name': filename})
        filename += '%2Exlsx'
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': 'web/content/?model=' + self._name + '&id=' + str(
                self.id) + '&field=file&download=true&filename=' + filename,
        }
