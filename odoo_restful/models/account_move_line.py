from odoo import models, api, fields, _

class AccountMoveLineInherit(models.Model):
    _inherit = "account.move.line"

    @api.model
    def _default_no_id(self):
        return str(self.move_id.id) + '-' + str(len(self.move_id.line_ids))


    no_id = fields.Char(string="No Id", default=_default_no_id)