# -*- coding: utf-8 -*-

from odoo import fields, api, models, _

class CountryDistrict(models.Model):
    _name = "res.country.district"

    name = fields.Char('Name', required=True)
    state_id = fields.Many2one('res.country.state', 'City', required=True)
    active = fields.Boolean('Active', default=True)
    ward_ids = fields.One2many('res.country.ward', 'district_id', string='Ward')

class CountryState(models.Model):
    _inherit = "res.country.state"

    district_ids = fields.One2many('res.country.district', 'state_id', string='Districts')

class CountryWard(models.Model):
    _name = "res.country.ward"

    name = fields.Char('Name', required=True)
    district_id = fields.Many2one('res.country.district', 'District', required=True)
    active = fields.Boolean('Active', default=True)
