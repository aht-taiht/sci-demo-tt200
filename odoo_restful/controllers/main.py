"""Part of odoo. See LICENSE file for full copyright and licensing details."""

import json
import logging
import dateutil.parser
from odoo import http
from odoo.http import request
from ..common import valid_response, invalid_response, prepare_response, extract_arguments
from ..helper import validate_token, validate_id, validate_model, parse_data, validate_data

_logger = logging.getLogger(__name__)

class APIController(http.Controller):
    """."""

    @validate_token
    @validate_id
    @validate_model
    @http.route('/sync/<model>/<id>', type='http', auth="none", methods=['GET'], csrf=False)
    def get(self, model=None, id=None):
        """Get record by id.
        Basic usage:
        import requests

        headers = {
            'charset': 'utf-8',
            'access-token': 'access_token'
        }
        model = 'res.partner'
        id = 100
        req = requests.get('{}/sync/{}/{}'.format(base_url, model, id), headers=headers)
        print(req.json())
        """
        try:
            record = request.env[model].sudo().browse(id)
            if model == 'hr.employee':
                fields = request.env[model].fields_get()
                return valid_response(prepare_response(record.read(fields=fields), one=True))
            elif record.read():
                return valid_response(prepare_response(record.read(), one=True))
            else:
                return invalid_response('missing_record',
                                        'record object with id %s could not be found' % (id, model), 404)
        except Exception as e:
            return invalid_response('exception', str(e))

    @validate_token
    @validate_model
    @http.route('/sync/<model>', type='http', auth="none", methods=['GET'], csrf=False)
    def search(self, model=None, **kwargs):
        """Get records by search query.
        Basic usage:
        import requests

        headers = {
            'content-type': 'application/x-www-form-urlencoded',
            'charset': 'utf-8',
            'access-token': 'access_token'
        }
        model = 'res.partner'
        data = {
            'domain': "[('supplier','=',True),('parent_id','=', False)]",
            'order': 'name asc',
            'limit': 10,
            'offset': 0,
            'fields': "['name', 'supplier', 'parent_id']"
        }
        ###
        #You can ommit unnessesary query params
        #data = {
        #    'domain': "[('supplier','=',True),('parent_id','=', False)]",
        #    'limit': 10
        #}
        ###
        #You can also use JSON-like domains
        #data = {
        #    'domain': "{'id':100, 'parent_id!':true}",
        #    'limit': 10
        #}
        req = requests.get('{}/sync/{}/'.format(base_url, model), headers=headers, params=data)
        print(req.json())
        """
        domain, fields, offset, limit, order = extract_arguments(kwargs)
        data = request.env[model].sudo().search_read(
                domain=domain, fields=fields, offset=offset, limit=limit, order=order)
        return valid_response(prepare_response(data))

    @validate_token
    @validate_id
    @validate_model
    @http.route('/get/account.move/err', type='http', auth="none", methods=['GET'], csrf=False)
    def get_account_move_err(self, model=None, id=None):
        try:
            query = ''' SELECT am.com_id FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id GROUP BY am.com_id HAVING ROUND(SUM(aml.credit) - SUM(aml.debit)) != 0 '''
            self.env.cr.execute(query, ())
            data = self.env.cr.fetchall()
            return valid_response({'ids': data})
        except Exception as e:
            return invalid_response('params', e)

    @validate_token
    @validate_model
    @parse_data
    @validate_data
    @http.route('/sync/<model>', type='json', auth="none", methods=['POST'], csrf=False)
    def create(self, model=None, **kwargs):
        try:
            data = self.convert_data(model, kwargs['data'])
            company_id = kwargs.pop('company_id', False)
            ids, data = self.check_update(model, company_id, data)
            if data:
                _model = request.env[model]
                if company_id:
                    _model = _model.with_company(company_id)
                for item in data:
                    company_id = item.get('company_id', company_id)
                    _model = _model.with_company(company_id)
                    item["synced"] = True
                    if model == "account.move" and item.get('state', False) == "posted":
                        item['state'] = "draft"
                        record = _model.sudo().with_company(company_id).create(item)
                        record.write({'state': 'posted'})
                    else:
                        if model == "res.users":
                            item['active'] = False
                        record = _model.sudo().with_company(company_id).create(item)
                    record.refresh()
                    ids = ids + record.ids
            return valid_response({'ids': ids})
        except Exception as e:
            return invalid_response('params', e)

    @validate_token
    @validate_id
    @validate_model
    @parse_data
    @validate_data
    @http.route('/sync/<model>/<id>', type='json', auth="none", methods=['PUT'], csrf=False)
    def put(self, model=None, id=None, **kwargs):
        try:
            record = request.env[model]
            company_id = kwargs.pop('company_id', False)
            company_id = kwargs['data'].get('company_id', company_id)
            if company_id:
                record = request.env[model].with_company(company_id)
            record = record.browse(id)
            if record.read():
                kwargs['data']['synced'] = True
                record.sudo().write(kwargs['data'])
                # if model == "account.move":
                #     record.line_ids.unlink()
                record.refresh()
                return valid_response({'id': record.id})
            else:
                return invalid_response('missing_record', 'record object with id %s could not be found' % id, 404)
        except Exception as e:
            return invalid_response('exception', str(e))

    @validate_token
    @validate_id
    @validate_model
    @parse_data
    @http.route('/sync/<model>/<id>/<action>', type='http', auth="none", methods=['PATCH'], csrf=False)
    def patch(self, model=None, id=None, action=None, **kwargs):
        """Call action for model.
        Basic usage:
        import requests

        headers = {
            'charset': 'utf-8',
            'access-token': 'access_token'
        }
        model = 'res.partner'
        id = 100
        action = 'delete'
        req = requests.patch('{}/sync/res.{}/{}'.format(base_url, model, id, action), headers=headers)
        print(req.content)
        """

        _logger.debug(f'Body: {kwargs}')
        for key, value in kwargs.items():
            if (isinstance(value, str)):
                if (value.startswith('[') & value.endswith(']')):
                    value = value.replace('[', '')
                    value = value.replace(']', '')
                    values_str = value.split(',')
                    values_int = []
                    for value in values_str:
                        values_int.append(int(value))
                    kwargs[key] = values_int

        try:
            record = request.env[model].sudo().browse(id)
            if record.read():
                _callable = action in [method for method in dir(
                    record) if callable(getattr(record, method))]
                if _callable:
                    # action is a dynamic variable.
                    if (kwargs):
                        action_result = getattr(record, action)(**kwargs)
                    else:
                        action_result = getattr(record, action)()
                if 'action_result' in vars() and isinstance(action_result, dict) and 'res_id' in action_result.keys():
                    record = request.env[model].sudo().browse(action_result['res_id'])
                else:
                    record.refresh()
                return valid_response(prepare_response(record.read(), one=True))
            else:
                return invalid_response('missing_record',
                                        'record object with id %s could not be found or %s object has no method %s' % (
                                        id, model, action), 404)
        except Exception as e:
            return invalid_response('exception', e, 503)

    @validate_token
    @validate_id
    @validate_model
    @http.route('/sync/<model>/<id>', type='json', auth="none", methods=['DELETE'], csrf=False)
    def delete(self, model=None, id=None):
        """Delete existing record.
        Basic usage:
        import requests

        headers = {
            'charset': 'utf-8',
            'access-token': 'access_token'
        }
        model = 'res.partner'
        id = 100
        req = requests.delete('{}/sync/{}/{}'.format(base_url, model, id), headers=headers)
        print(req.json())
        """

        try:
            record = request.env[model].sudo().search([('com_id', '=', int(id))])
            if record.read():
                record.unlink()
                return valid_response({'success': True})
            else:
                return invalid_response('missing_record', 'record object with id %s could not be found' % id, 404)
        except Exception as e:
            return invalid_response('exception', str(e), 503)

    def convert_data(self, model, data):
        return data

    def check_update(self, model, company_id, data):
        m_model_c = {'account.account': ['code', 'company_id', 'com_id'], 'res.partner': ['com_id'], 'product.template': ['default_code', 'com_id'], 'res.company': ['code', 'com_id'], 'product.product': ['product_tmpl_id', 'combination_indices', 'default_code'], 'res.currency': ['name'], 'product.template.attribute.line': ['attribute_id', 'product_tmpl_id', 'com_id'], 'product.attribute': ['sequence', 'com_id'], 'product.attribute.value': ['attribute_id', 'sequence', 'com_id'], 'product.template.attribute.value': ['attribute_id', 'attribute_line_id', 'product_attribute_value_id', 'product_tmpl_id'], 'res.country': ['name'], 'res.country.state': ['code', 'country_id'], 'res.partner.bank': ['partner_id', 'com_id'], 'res.bank': ['bic', 'com_id'], 'account.journal': ['code', 'name', 'company_id', 'com_id'], 'account.move': ['com_id'], 'account.move.line': ['com_id'], 'res.users': ['login']}
        ids = []
        if m_model_c.get(model, False):
            fields = m_model_c.get(model)
            for val in data:
                company_id = val.get('company_id', company_id)
                domain = [(field, '=', val[field]) for field in fields if not (val.get(field, False) == False and isinstance(val.get(field, False), bool))]
                if domain:
                    if not model in ['account.move', 'account.move.line', 'res.company', 'account.account']:
                        domain.append(('active','in',[True, False]))
                    rec = request.env[model].with_company(company_id).sudo().search(domain, limit=1)
                    if rec:
                        rec.write(val)
                        ids.append(rec.id)
                        data.remove(val)
        return ids, data
