{
    'name': "Onnet - EInvoice Viettel",

    'summary': """
            Onnet - EInvoice Viettel
        """,
    'description': """
        Onnet - EInvoice Viettel
    """,
    'category': 'Accounting',
    'version': '17.0.1.1',
    'author': "Onnet",
    "depends": ['onnet_vat_base'],
    "data": [
        'security/ir.model.access.csv',
        'data/einvoice_data.xml',
        'view/einvoice_viettel_branch_views.xml',
        'view/res_partner_views.xml',
        'view/res_users_views.xml',
        'view/account_vat_invoice_views.xml',
        'view/account_move_views.xml'
    ],
    "license": "LGPL-3",
    'installable': True,
}
