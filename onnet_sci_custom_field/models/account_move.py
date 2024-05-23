from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.addons.base.models import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF


class AccountMove(models.Model):
    _inherit = 'account.move'

    patient = fields.Many2one('sh.medical.patient', string='Tên bệnh nhân', help="Tên bệnh nhân")
    invoice_payment_state = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')],
        string='Payment', store=True, readonly=True, copy=False, tracking=True)
    invoice_payment_ref = fields.Char(string='Payment Reference', index=True, copy=False,
                                      help="The payment reference to set on journal items.")