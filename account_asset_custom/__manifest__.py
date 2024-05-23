# -*- coding: utf-8 -*-
{
    'name': "Assets Management Custom",

    'summary': """
        Assets Management Custom""",

    'description': """
        Customize Assets Management
    """,

    'author': "TuUH",
    'category': 'Accounting/Accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['account_asset', 'onnet_sci_custom_field', 'hr'],

    # always loaded
    'data': [
        'views/account_asset.xml',
        'views/account_asset_sell.xml',
        'views/res_currency.xml',
    ],
}
