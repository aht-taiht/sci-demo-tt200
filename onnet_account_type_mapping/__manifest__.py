# -*- coding: utf-8 -*-
{
    'name': 'Onnet Offset Account',
    'version': '17.0.1.0',
    'author': 'Onnet Consulting',
    'website': 'https://on.net.vn',
    'category': 'Accounting/Accounting',
    'depends': ['account',
                ],
    'data': [
        'security/ir.model.access.csv',
        'data/account_account_type_data.xml',
        'data/account_type_mapping_data.xml',
        'views/account_type_mapping_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
