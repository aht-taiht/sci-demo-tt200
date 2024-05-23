import functools
import json

import dateutil.parser

from odoo.http import request
from .common import invalid_response


def validate_token(func):
    """."""

    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        """."""
        access_token = request.httprequest.headers.get('access_token')
        if not access_token:
            return invalid_response('access_token_not_found', 'missing access token in request header', 401)
        access_token_data = request.env['api.access_token'].sudo().search(
            [('token', '=', access_token)], order='id DESC', limit=1)

        if access_token_data.find_one_or_create_token(user_id=access_token_data.user_id.id) != access_token:
            return invalid_response('access_token', 'token seems to have expired or invalid', 401)

        request.session.uid = access_token_data.user_id.id
        request.uid = access_token_data.user_id.id
        return func(self, *args, **kwargs)

    return wrap


def validate_id(func):
    """."""

    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        """."""
        id = kwargs['id']
        try:
            kwargs['id'] = int(id)
        except Exception as e:
            return invalid_response('invalid object id', 'invalid id %s' % id)
        else:
            return func(self, *args, **kwargs)

    return wrap


def validate_model(func):
    """."""

    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        """."""
        model = kwargs['model']
        _model = request.env['ir.model'].sudo().search(
            [('model', '=', model)], limit=1)
        if not _model:
            return invalid_response('invalid object model', 'The model %s is not available in the registry.' % model,
                                    404)
        return func(self, *args, **kwargs)

    return wrap


def parse_data(func):
    """."""

    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        """."""
        result = {}
        for key, value in kwargs.items():
            converted_value = value
            if isinstance(value, str):
                if value in ['true', 'True']:
                    converted_value = True
                elif value in ['false', 'False']:
                    converted_value = False
                else:
                    try:
                        converted_value = int(value)
                    except Exception:
                        try:
                            converted_value = dateutil.parser.parse(value)
                        except Exception:
                            pass
            result[key] = converted_value
        return func(self, *args, **result)

    return wrap


def validate_data(func):
    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        model = kwargs['model']
        payload = json.loads(request.httprequest.get_data().
                             decode(request.httprequest.charset))
        map_field = {'product.template': ['default_code', 'name'],
                     'accessory_product_ids': ['categ_id', 'cost_currency_id', 'uom_id', 'uom_po_id', 'uom_so_id',
                                               'code'],
                     'product.pricelist': ['brand_id', 'display_name', 'name', 'start_date'],
                     'duct.template.attribute.value': ['display_name', 'name'],
                     'product.category': ['property_account_creditor_price_difference_categ',
                                          'property_account_expense_categ_id', 'property_account_income_categ_id',
                                          'property_stock_account_input_categ_id',
                                          'property_stock_account_output_categ_id',
                                          'property_stock_valuation_account_id', 'code', 'complete_name',
                                          'display_name', 'name', 'property_cost_method', 'property_valuation'],
                     'res.currency': ['rate_ids', 'currency_subunit_label', 'currency_unit_label', 'rate', 'rounding',
                                      'decimal_places'],
                     'project.project': ['display_name', 'name', 'billable_type', 'date_start'],
                     'res.partner': ['property_purchase_currency_id', 'code_customer', 'name', 'ref', 'acc_holder_name',
                                     'acc_number', 'bank_name', 'display_name', 'acc_type'],
                     'res.partner.category': ['display_name', 'name'],
                     'res.company': ['display_name', 'name'],
                     'res.country': ['code', 'display_name', 'name', 'phone_code'],
                     'res.country.district': ['ward_ids', 'display_name', 'name', 'state_id'],
                     'res.users': ['company_id', 'company_ids', 'contract_ids', 'currency_id',
                                   'property_account_payable_id', 'property_account_receivable_id', 'display_name',
                                   'name'],
                     'account.account': ['code', 'display_name', 'name'],
                     'account.move': ['invoice_payment_ref', 'ref',
                                      'invoice_payment_state', 'state', 'date', 'invoice_date', 'invoice_date_due',
                                      'amount_tax', 'amount_total', 'amount_untaxed'],
                     'account.tax': ['cash_basis_base_account_id', 'cash_basis_transition_account_id', 'display_name',
                                     'name', 'amount'],
                     'account.payment.term': ['line_ids', 'display_name', 'name'],
                     'account.analytic.account': ['code', 'display_name', 'name', 'balance', 'credit', 'debit'],
                     'account.analytic.line': ['so_line', 'code', 'display_name', 'name', 'ref', 'amount']}

        kwargs['company_id'] = payload.get('company_id', False)

        if isinstance(payload['data'], list):
            for item in payload['data']:
                for field in item:
                    item[field] = convert_currency_field(model, field, item[field], kwargs['company_id'])
                    if model == 'account.account':
                        if field == 'type_third_parties' and item[field] == 'false':
                            item[field] = 'no'
                        rec_pay_acc = request.env['account.account.type'].sudo().search([('type', 'in', ('receivable', 'payable'))]).ids
                        if field == 'reconcile' and item[field] == False and rec_pay_acc and item['user_type_id'] in rec_pay_acc:
                            item[field] = True
        else:
            for field in payload['data']:
                payload['data'][field] = convert_currency_field(model, field, payload['data'][field], kwargs['company_id'])

        kwargs['data'] = payload['data']

        return func(self, *args, **kwargs)

    return wrap

def convert_account_field(model, field, value, company_id):

    account_account_fields = {
        'product.category': ['property_account_creditor_price_difference_categ', 'property_account_expense_categ_id',
                              'property_account_income_categ_id', 'property_stock_account_input_categ_id',
                              "property_stock_account_output_categ_id", "property_stock_valuation_account_id"],
        'project.project': ['analytic_account_id'],
        'res.company': ['account_default_pos_receivable_account_id', 'default_cash_difference_expense_account_id', 'default_cash_difference_income_account_id', 'expense_accrual_account_id', 'expense_currency_exchange_account_id', 'income_currency_exchange_account_id', 'revenue_accrual_account_id', 'transfer_account_id'],
        'res.users': ['property_account_payable_id', 'property_account_receivable_id'],
        'account.move.line': ['account_id'],
        'account.tax': ['cash_basis_transition_account_id']
    }

    if account_account_fields.get(model, False) and field in account_account_fields[model] and isinstance(value, str):
        model = request.env['account.account']
        if company_id:
            model = model.with_company(company_id)
        account = model.sudo().search(
            [('code', '=', value)], order='id DESC', limit=1)
        if account:
            return account.id
        else:
            return False
    return value

def convert_product_category_field(model, field, value, company_id):

    product_category_fields = {
        'product.category': ['parent_id'],
        'product.template': ['categ_id'],
        'product.product': ['categ_id'],
    }

    if product_category_fields.get(model, False) and field in product_category_fields[model] and isinstance(value, str):
        model = request.env['product.category']
        if company_id:
            model = model.with_company(company_id)
        cate = model.sudo().search(
            [('code', '=', value)], order='id DESC', limit=1)
        if cate:
            return cate.id
        else:
            return False
    return value

def convert_currency_field(model, field, value, company_id):

    currency_fields = {
        'product.product': ['cost_currency_id'],
        'res.partner': ['property_purchase_currency_id'],
        'res.users': ['currency_id']
    }

    if currency_fields.get(model, False) and field in currency_fields[model] and isinstance(value, str):
        model = request.env['res.currency']
        if company_id:
            model = model.with_company(company_id)
        currency = model.sudo().search(
            [('name', '=', value)], order='id DESC', limit=1)
        if currency:
            return currency.id
        else:
            return False
    return value

def convert_uom_field(model, field, value, company_id):

    uom_fields = {
        'product.product': ['uom_id', 'uom_po_id'],
        'product.template': ['uom_id', 'uom_po_id'],
        'account.move.line': ['product_uom_id']
    }

    if uom_fields.get(model, False) and field in uom_fields[model] and isinstance(value, str):
        model = request.env['uom.uom']
        if company_id:
            model = model.with_company(company_id)
        uom = model.sudo().search(
            [('name', '=', value)], order='id DESC', limit=1)
        if uom:
            return uom.id
        else:
            return False
    return value

def convert_product_tml_field(model, field, value, company_id):

    product_tml_fields = {
    }

    if product_tml_fields.get(model, False) and field in product_tml_fields[model] and isinstance(value, str):
        model = request.env['product.template']
        if company_id:
            model = model.with_company(company_id)
        product = model.sudo().search(
            [('default_code', '=', value)], order='id DESC', limit=1)
        if product:
            return product.id
        else:
            return False
    return value

def convert_journal_field(model, field, value, company_id):

    journal_fields = {
        'res.partner.bank': ['journal_id'],
        'res.company': ['account_opening_journal_id', 'account_opening_move_id', 'tax_cash_basis_journal_id']
    }

    if journal_fields.get(model, False) and field in journal_fields[model] and isinstance(value, str):
        model = request.env['account.journal']
        if company_id:
            model = model.with_company(company_id)
        journal = model.sudo().search(
            [('name', '=', value)], order='id DESC', limit=1)
        if journal:
            return journal.id
        else:
            return False
    return value

def convert_company_field(model, field, value, company_id):

    company_fields = {
        'res.users': ['company_id'],
        'account.move': ['company_id'],
        'account.move.line': ['company_id'],
        'account.tax': ['company_id'],
        'account.payment.term': ['account.payment.term'],
        'account.analytic.account': ['account.analytic.account'],
        'account.analytic.line': ['company_id'],
        'account.account': ['company_id']
    }

    if company_fields.get(model, False) and field in company_fields[model] and isinstance(value, str):
        model = request.env['res.company']
        if company_id:
            model = model.with_company(company_id)
        company = model.sudo().search(
            [('code', '=', value)], order='id DESC', limit=1)
        if company:
            return company.id
        else:
            return False
    return value

def convert_product_field(model, field, value, company_id):

    product_fields = {
        'account.move.line': ['product_id', ]
    }

    if product_fields.get(model, False) and field in product_fields[model] and isinstance(value, str):
        model = request.env['product.product']
        if company_id:
            model = model.with_company(company_id)
        product = model.sudo().search(
            [('default_code', '=', value)], order='id DESC', limit=1)
        if product:
            return product.id
        else:
            return False
    return value

def convert_analytic_account_field(model, field, value, company_id):

    analytic_account_fields = {
        'account.analytic.line': ['account_id', ]
    }

    if analytic_account_fields.get(model, False) and field in analytic_account_fields[model] and isinstance(value, str):
        model = request.env['account.analytic.account']
        if company_id:
            model = model.with_company(company_id)
        analytic_account = model.sudo().search(
            [('code', '=', value)], order='id DESC', limit=1)
        if analytic_account:
            return analytic_account.id
        else:
            return False
    return value
