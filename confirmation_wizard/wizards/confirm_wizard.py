# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ConfirmWizard(models.TransientModel):
    _name = 'confirm.wizard'

    message = fields.Text("Message", required=True)
    res_model = fields.Char("Model")
    active_ids = fields.Char("Active IDs")
    method = fields.Char("Method")

    def action_confirm(self):
        if self.res_model and self.method and self.active_ids:
            method_func = getattr(self.env[self.res_model], self.method)
            active_ids = eval(self.active_ids)
            if method_func:
                method_func(active_ids)
