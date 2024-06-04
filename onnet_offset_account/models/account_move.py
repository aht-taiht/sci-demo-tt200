from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _set_offset_account(self):
        for move in self:
            move.line_ids._set_offset_account()


