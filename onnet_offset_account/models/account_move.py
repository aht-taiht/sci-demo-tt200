from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.constrains('line_ids')
    def constraint_many_debit_credit(self):
        for rec in self:
            _error_message = ("Can not compute offset accounts when have many debit and credit item at the same time")
            debit_count = len(rec.line_ids.filtered(lambda x: x.balance > 0))
            credit_count = len(rec.line_ids.filtered(lambda x: x.balance < 0))
            if debit_count > 1 and credit_count > 1 and rec.state == 'draft' and rec.move_type == 'entry':
                raise ValidationError(_error_message)


