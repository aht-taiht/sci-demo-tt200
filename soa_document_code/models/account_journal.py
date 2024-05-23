import ast
import json
from collections import defaultdict
from datetime import timedelta

from odoo import api, Command, fields, models, _, _lt
from odoo.addons.rating.models import rating_data
from odoo.exceptions import UserError
from odoo.tools import get_lang, SQL


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    sequence_id = fields.Many2one('ir.sequence', 'Sequence', ondelete='restrict')

    def _create_account_move_seq(self):
        self.ensure_one()
        if self.sequence_id:
            return
        if self.type == 'sale':
            prefix = 'CI%(y)s'
        elif self.type == 'purchase':
            prefix = 'BILL%(y)s'
        elif self.type in ['bank', 'cash']:
            prefix = f'{self.code}%(y)s'
        else:
            prefix = f'{self.code}%(y)s'

        # The sequence which has the same prefix used for the multiple companies
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', self._name),
            ('prefix', '=', prefix)
        ])
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': _('Journal Sequence: %s') % self.name,
                'code': self._name,
                'prefix': prefix,
                'padding': 5,
            })
        self.sequence_id = sequence
