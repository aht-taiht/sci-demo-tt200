import base64
from io import BytesIO

import xlsxwriter

from odoo import models, fields


class RevenueProductCategoryReport(models.TransientModel):
    _name = "revenue.product.category.report"
    _description = "Revenue Product Category Report"

    file = fields.Binary('Click On Download Link To Download Xls File', readonly=True)
    name = fields.Char(string='File Name', size=64)

    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='End Date')

    def get_data(self):
        query = f"""
            select e.name as dichvu, sum(a.credit) as doanhthu from account_move_line a
            left join account_account b on b.id = a.account_id
            left join product_product c on c.id = a.product_id
            left join product_template d on d.id = c.product_tmpl_id
            left join product_category e on e.id = d.categ_id
            WHERE b.code like '511%'   
            and a.company_id  = {self.env.company.id}
            and a.date >= '{self.date_from}'
            and a.date <= '{self.date_to}' 
            group by dichvu
        """
        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()
        return data

    def action_print(self):
        self.ensure_one()
        fl = BytesIO()
        wb = xlsxwriter.Workbook(fl)

        sheet1 = wb.add_worksheet('Báo cáo doanh thu theo nhóm sản phẩm dịch vụ')

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

        right_normal_date = wb.add_format({
            'valign': 'middle',
            'align': 'right',
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
        sheet1.write(1, 1, 'BÁO CÁO DOANH THU THEO TỪNG NHÓM SẢN PHẨM DỊCH VỤ', header_title)
        sheet1.write(2, 1,
                     'From: ' + self.date_from.strftime("%Y-%m-%d") + '   To: ' + self.date_to.strftime("%Y-%m-%d"),
                     header_normal)

        sheet1.write(4, 0, 'STT', header_table)
        sheet1.write(4, 1, 'DỊCH VỤ', header_table)
        sheet1.set_column(4, 2, 15)
        sheet1.write(4, 2, 'DOANH THU', header_table)

        data = self.get_data()

        def print_assets(i, lines, strat_no=0):
            for line in lines:
                i += 1
                sheet1.write(4 + i, 0, i - strat_no, center_normal)
                sheet1.write(4 + i, 1, line.get('dichvu', ''), left_normal)
                sheet1.write(4 + i, 2, line.get('doanhthu', ''), right_number_normal)
            return i

        i = 1
        sheet1.set_row(4 + i, cell_format=left_bold)
        print_assets(i, data, 1)
        wb.close()
        buf = base64.b64encode(fl.getvalue())
        fl.close()

        filename = "bao_cao_doanh_thu_theo_nhom_san_pham_dich_vu"
        self.write({'file': buf, 'name': filename})
        filename += '%2Exlsx'
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': 'web/content/?model=' + self._name + '&id=' + str(
                self.id) + '&field=file&download=true&filename=' + filename,
        }
