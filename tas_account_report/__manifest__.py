{
    'name': 'Enterprise account report',
    'summary': """Enterprise account report """,

    'description': """
        Tas account report
    """,
    'author': "TASYS",
    'website': "",
    'category': 'tasys',
    'version': '1.0',
    'depends': ['base',  'account', 'account_reports', 'onnet_offset_account'],
    'images': [
    ],
    'data': [
        'views/account_account.xml',
        'views/account_financial_html_report_line_view.xml',
        'views/custom_search_template_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'OEEL-1',
}
