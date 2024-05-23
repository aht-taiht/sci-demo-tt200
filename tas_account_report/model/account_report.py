# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    @api.model
    def _get_dates_period(self, options, date_from, date_to, mode, period_type=None, strict_range=False):
        output = super(AccountReport, self)._get_dates_period(options, date_from, date_to, mode, period_type, strict_range)

        if output.get('period_type') == 'month':
            if self.env.user.lang == 'vi_VN':
                string = format_date(self.env, fields.Date.to_string(date_to), date_format='MM yyyy')
                output['string'] = 'Tháng ' + string

        return output
