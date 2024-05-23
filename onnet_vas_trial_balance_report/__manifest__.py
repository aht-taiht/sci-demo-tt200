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
        'data/account_group_data.xml',
        # 'data/chart_of_account.xml',
        'data/vas_trial_balance_report.xml',
        'data/account_report_action.xml',
        'view/account_account_views.xml',
        'view/menu.xml',
    ],
    "license": "LGPL-3",
    'installable': True,
}
