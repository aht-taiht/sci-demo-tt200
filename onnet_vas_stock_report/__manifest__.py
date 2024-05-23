{
    'name': "Onnet - VAS Stock Report",

    'summary': """
            Onnet - VAS Stock Report
        """,
    'description': """
        Onnet - VAS Stock Report
    """,
    'category': 'Accounting',
    'version': '17.0.1.1',
    'author': "Onnet",
    'depends': [
        'onnet_vas_base',
        'stock'
    ],
    "data": [
        # Security
        'security/ir.model.access.csv',
        'wizards/inventory_report_activities_wizard.xml',
        'view/menu_views.xml'
    ],
    "license": "LGPL-3",
    'installable': True,
}
