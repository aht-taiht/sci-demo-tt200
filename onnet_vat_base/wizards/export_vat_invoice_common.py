# -*- coding: utf-8 -*-
import io
import re
import keyword
import xlsxwriter

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import expr_eval

MONTHS = [('1', _('Jan')), ('2', _('Feb')), ('3', _('Mar')), ('4', _('Apr')), ('5', _('May')), ('6', _('Jun')),
          ('7', _('Jul')), ('8', _('Aug')), ('9', _('Sep')), ('10', _('Oct')), ('11', _('Nov')), ('12', _('Dec'))]

QUARTERS = [('1', _('First quarter')), ('2', _('Second quarter')),
            ('3', _('Third quarter')), ('4', _('Fourth quarter'))]


def get_years():
    year_list = [str(num) for num in range(datetime.now().year - 20, datetime.now().year + 2)]
    year_list = sorted(year_list, reverse=True)
    return [(element, element) for element in year_list]


class ExportVATInvoiceCommon(models.AbstractModel):
    _name = 'export.vat.invoice.common'
    _description = 'Export Vat Invoice common'

    year = fields.Selection(get_years(), string='Year')
    period = fields.Selection([
        ('month', 'Month'),
        ('quarter', 'Quarter')
    ], string='Period', default='month', copy=False)
    month = fields.Selection(MONTHS, string="Month", copy=False)
    quarter = fields.Selection(QUARTERS, string="Quarter", copy=False)
    date_from = fields.Date(string="From", required=True)
    date_to = fields.Date(string="To", required=True)

    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(ExportVATInvoiceCommon, self).default_get(fields_list)
        starting_day_of_current_year = datetime.now().date().replace(day=1)
        ending_day_of_current_year = starting_day_of_current_year + relativedelta(months=1) + relativedelta(days=-1)
        res['year'] = str(datetime.now().year)
        res['month'] = str(datetime.now().month)
        res['date_from'] = starting_day_of_current_year
        res['date_to'] = ending_day_of_current_year
        return res

    @api.constrains('date_from', 'date_to')
    def check_constrains_fields(self):
        for wizard in self:
            if not wizard.date_from or not wizard.date_to:
                raise UserError(_('Date From and Date to must be required !'))

    def _check_date_time_range(self):
        if self.date_from and self.date_to and self.date_from.year != self.date_to.year:
            raise ValidationError(_('You can only view the report with in the same year !'))

    @api.onchange('date_from', 'date_to')
    def _onchange_from_date_to(self):
        if self.date_from and self.date_to:
            self._check_date_time_range()
            if self.date_from > self.date_to:
                raise ValidationError(_('From date must be less than To date !'))

    @api.onchange('year', 'period', 'month', 'quarter')
    def _onchange_period_date(self):
        if self.year:
            if self.period == 'month' and self.month:
                self.date_from = datetime(year=int(self.year), month=int(self.month), day=1)
                self.date_to = self.date_from + relativedelta(months=1) + relativedelta(days=-1)
            elif self.period == 'quarter' and self.quarter:
                if self.quarter == '1':
                    self.date_from = datetime(year=int(self.year), month=1, day=1)
                    self.date_to = datetime(year=int(self.year), month=3, day=31)
                elif self.quarter == '2':
                    self.date_from = datetime(year=int(self.year), month=4, day=1)
                    self.date_to = datetime(year=int(self.year), month=6, day=30)
                elif self.quarter == '3':
                    self.date_from = datetime(year=int(self.year), month=7, day=1)
                    self.date_to = datetime(year=int(self.year), month=9, day=30)
                else:
                    self.date_from = datetime(year=int(self.year), month=10, day=1)
                    self.date_to = datetime(year=int(self.year), month=12, day=31)
            else:
                self.date_from = datetime(year=int(self.year), month=1, day=1)
                self.date_to = datetime(year=int(self.year), month=12, day=31)
        else:
            self.date_from = False
            self.date_to = False

    def _get_report_name(self):
        return _('Export Vat Invoice')

    def _inject_report_into_xlsx_sheet(self, workbook, sheet):
        """"""

    def get_xlsx(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })

        self._inject_report_into_xlsx_sheet(workbook, workbook.add_worksheet(self._get_report_name()))

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        # Debug block code
        # with open("output.xlsx", "wb") as f:
        #     f.write(generated_file)
        output.close()
        return {
            'file_name': f'{self._get_report_name()}.xlsx',
            'file_content': generated_file,
            'file_type': 'xlsx',
        }

    def action_export_to_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/download/xlsx/%s/%s/%s' % (
                'ExportVatInvoice', self._name, self.id)
        }
