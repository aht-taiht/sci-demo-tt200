
from odoo import api, Command, fields, models, _, _lt
import datetime


class Project(models.Model):
    _inherit = 'project.project'

    name = fields.Char(
        "Name", index='trigram', required=True, tracking=True, translate=True, default_export_compatible=True,
        default=lambda self: _('New'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'company_id' in vals:
                self = self.with_company(vals['company_id'])
            if vals.get('analytic_account_id'):
                vals['name'] = self.env['account.analytic.account'].browse(vals.get('analytic_account_id')).name
            elif _("New") in vals.get('name', _("New")):
                seq_date = fields.Datetime.context_timestamp(
                    self, fields.Datetime.today()
                )
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'project.project', sequence_date=seq_date) or _("New")
        res = super(Project, self).create(vals_list)

        for project in res:

            if project.partner_id:
                if project.name:
                    year = int(project.name[-4:-2]) + 2000
                    create_date = datetime.date(year, 1, 1)
                else:
                    year = project.create_date.strftime('%Y')
                    create_date = project.create_date

                partner_project_index_obj = self.env['partner.project.index']
                index_record = partner_project_index_obj.search([
                    ('partner_id', 'parent_of', project.partner_id.id),
                    ('year', '=', year)
                ], limit=1, order='year desc, current_project_index desc')
                if not index_record:
                    index_record = partner_project_index_obj.create({
                        'partner_id': project.partner_id.commercial_partner_id.id,
                        'year': year,
                        'date': create_date.strftime('%Y-%m-%d'),
                        'project_id': project.id
                    })
                index_record.current_project_index += 1
        return res
