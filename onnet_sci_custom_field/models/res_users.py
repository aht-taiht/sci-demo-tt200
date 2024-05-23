from odoo import api, fields, models, _

class ResUsers(models.Model):
    _inherit = "res.users"

    # physician_ids = fields.One2many('sh.medical.physician', 'sh_user_id', string='Physicians', auto_join=True)
    # user_line = fields.One2many('op.student', 'user_id', 'User Line')
    child_ids = fields.Many2many(
        'res.users', 'res_user_first_rel1',
        'user_id', 'res_user_second_rel1', string='Childs')
    # institution = fields.Many2many('sh.medical.health.center', 'sh_users_health_center_rel', 'user_id', 'ins_id',
    #                                string="Cơ sở y tế", store=True)

    # def create_user(self, records, user_group=None):
    #     for rec in records:
    #         if not rec.user_id:
    #             user_vals = {
    #                 'name': rec.name,
    #                 'login': rec.email or (rec.name + rec.last_name),
    #                 'partner_id': rec.partner_id.id
    #             }
    #             user_id = self.create(user_vals)
    #             rec.user_id = user_id
    #             if user_group:
    #                 user_group.users = user_group.users + user_id
    #
    # @api.model
    # def fetch_export_models(self):
    #     """Gets all models where the user has export access."""
    #     accessobj = self.env["ir.model.access"]
    #     accessobj_ids = accessobj.search(
    #         [("perm_export", "=", True), ("group_id", "in", self.groups_id.ids)]
    #     )
    #     model_names = [access_obj.model_id.model for access_obj in accessobj_ids]
    #     return list(set(model_names))