# -*- coding: utf-8 -*-
{
    'name': 'Onnet Finance TT200 Report',
    'category': 'Accounting/Accounting',
    'description': """
""",
    'depends': [
        'onnet_vas_base'
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Data
        'data/account_report_action.xml',
        # 'data/chart_account_data.xml',
        # Wizard
        'wizards/trial_balance_wizard_views.xml',
        'wizards/general_journal_wizard_views.xml',
        'wizards/ledger_journal_wizard_views.xml',
        # View
        # Menu
        'menu/menu.xml'
    ],
    'license': 'OEEL-1',
}
