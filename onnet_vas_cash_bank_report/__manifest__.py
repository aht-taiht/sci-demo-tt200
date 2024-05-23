{
    'name': "Onnet - VAS Cash/Bank Report",

    'summary': """
            Onnet - VAS Cash/Bank Report
        """,
    'description': """
        Onnet - VAS Cash/Bank Report
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
        'data/cash_book_report.xml',
        'data/bank_book_report.xml',
        'data/account_report_action.xml',
        'view/menu_views.xml'
    ],
    "license": "LGPL-3",
    'installable': True,
}
