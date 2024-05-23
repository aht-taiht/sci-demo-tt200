import json
from datetime import datetime

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class APIAccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    booking_name = fields.Char(string='Tên Booking')
    source_name = fields.Char(string='Nguồn Booking')
    user_name = fields.Char(string='Tư vấn viên')

