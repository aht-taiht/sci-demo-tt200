from odoo import models, fields

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    code = fields.Char(size=10)
    internal_transfer = fields.Boolean('Internal Transfer')