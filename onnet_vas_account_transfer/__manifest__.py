# -*- coding: utf-8 -*-
{
    'name': "Onnet - VAS Account Transfer",

    'summary': "Onnet - VAS Account Transfer",

    'description': """
        Onnet - VAS Account Transfer
    """,

    'author': "Onnet",

    'category': 'Accounting',
    'version': '17.0.1.1',

    # any module necessary for this one to work correctly
    'depends': ['onnet_vas_base', 'onnet_vas_trial_balance_report'],

    # always loaded
    'data': [
        'data/ir_sequence_data.xml',
        'security/ir.model.access.csv',
        'wizard/vas_account_transfer_wizard.xml',
        'views/account_account_views.xml',
        'views/vas_account_closing_entry_views.xml',
        'views/vas_account_transfer_views.xml',
        'views/menu.xml',
    ],
    # only loaded in demonstration mode
    'installable': True,
    'application': True,
}

