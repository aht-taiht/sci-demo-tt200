# -*- coding: utf-8 -*-

from datetime import timedelta, datetime

from odoo import api, Command, fields, models, _, _lt
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    project_index_ids = fields.One2many(
        'partner.project.index', 'partner_id', 'Partner Project Index')

    def get_project_index_line(self, year: datetime):
        self.ensure_one()
        return self.project_index_ids.filtered(lambda line: line.year == year.year)


class PartnerProjectIndex(models.Model):
    _name = 'partner.project.index'
    _description = 'Partner Project Index'
    _order = 'year desc, current_project_index desc'

    partner_id = fields.Many2one('res.partner', 'Partner', index=1)
    project_id = fields.Many2one('project.project', 'Project')
    date = fields.Date('Date')
    year = fields.Integer('Year', index=1)
    current_project_index = fields.Integer('Current Project Index', default=0)


class PartnerSaleAnalyticIndex(models.Model):
    _name = 'partner.analytic.index'
    _description = 'Partner Sale Analytic Index'

    partner_id = fields.Many2one('res.partner', 'Partner', index=1)
    analytic_id = fields.Many2one('account.analytic.account', 'Analytic')
    year = fields.Integer('Year', index=1)
    current_index = fields.Integer('Current Analytic Index', default=0)


class PartnerPurchaseAnalyticIndex(models.Model):
    _name = 'partner.purchase.analytic.index'
    _description = 'Partner Purchase Analytic Index'

    partner_id = fields.Many2one('res.partner', 'Partner', index=1)
    analytic_id = fields.Many2one('account.analytic.account', 'Analytic')
    year = fields.Integer('Year', index=1)
    current_index = fields.Integer('Current Analytic Index', default=0)
