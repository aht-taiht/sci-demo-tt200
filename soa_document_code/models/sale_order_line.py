# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import models, api, fields, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _timesheet_create_project_prepare_values(self):
        """Inherit Odoo base method"""
        result = super(SaleOrderLine, self)._timesheet_create_project_prepare_values()
        result['description'] = Markup('<p>%s</p>' % result['name'])
        result['name'] = _('New')
        if result.get('partner_id'):
            partner = self.env['res.partner'].browse(result['partner_id'])
            result['partner_id'] = partner.commercial_partner_id.id
        return result
