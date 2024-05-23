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
    'depends': [
        'account_reports',
        'onnet_offset_account'
    ],
    "data": [
        'security/ir.model.access.csv',
        'view/menu_views.xml'
    ],
    "license": "LGPL-3",
    'installable': True,
}
