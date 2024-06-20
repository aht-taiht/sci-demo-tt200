from odoo import models, fields, _
from dateutil.relativedelta import relativedelta
from itertools import chain
class AgedPartnerBalanceCustomHandlerCustom(models.AbstractModel):
    _inherit = 'account.aged.partner.balance.report.handler'


