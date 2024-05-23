{
    'name': "Onnet - VAS Base",

    'summary': """
            Onnet - VAS Base
        """,
    'description': """
        Onnet - VAS Base
    """,
    'category': 'Accounting',
    'version': '17.0.1.1',
    'author': "Onnet",
    "depends": ['account'],
    "data": [
        'security/ir.model.access.csv',
        'security/vat_invoice_security.xml',
        'view/account_vat_invoice_views.xml',
        'view/account_move.xml',
        'wizards/export_vat_out_invoice_wizard.xml',
        'wizards/export_vat_in_invoice_wizard.xml',
        'view/menu_views.xml'
    ],
    "license": "LGPL-3",
    'installable': True,
}
