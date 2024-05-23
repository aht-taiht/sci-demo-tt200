{
    'name': 'Internal Transfer',
    'author': 'TaiHT',
    'summary': 'Sync account move',
    'depends': [
        'account_accountant',
        'odoo_restful'
    ],
    'data': [
        'views/res_currency.xml',
    ],
    'installable': True,
    'auto_install': True,
}
