# -*- coding: utf-8 -*-
import logging
import uuid

from odoo import api, fields, models
from odoo.http import request

_logger = logging.getLogger(__name__)


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    def _next(self, sequence_date=None):
        # Not executing _do_next for sequence when testing import
        try:
            if hasattr(request, 'params'):
                import_test = request.params.get('kwargs', {}).get('dryrun', False)
                if import_test:
                    print('except =======================')
                    code = uuid.uuid4().hex
                    return code
        except RuntimeError as e:
            _logger.info('Exception while access request object')
        return super(IrSequence, self)._next(sequence_date)
