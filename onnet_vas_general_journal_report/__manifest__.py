{
    'name': "Onnet - VAS Trial Balance Report",

    'summary': """
            Onnet - VAS Trial Balance Report
        """,
    'description': """
        Onnet - VAS Trial Balance Report
    """,
    'category': 'Accounting',
    'version': '17.0.1.1',
    'author': "Onnet",
    'depends': [
        'onnet_vas_base'
    ],
    "data": [
        # Security
        'security/ir.model.access.csv',
        # Data
        'data/vas_general_journal_report.xml',
        'data/account_report_action.xml',
        'view/menu.xml',
    ],
    "license": "LGPL-3",
    'installable': True,
}
