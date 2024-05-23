# -*- coding: utf-8 -*-
{
    'name': 'SOA Financial Report',
    'category': 'Accounting/Accounting',
    'description': """
""",
    'depends': [
        'account_budget',
        'account_reports',
        'account_payment',
        'soa_sale_management',
        'confirmation_wizard',
        'stock'
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/cashflow_security.xml',
        # Data
        'data/fs_combined_pl.xml',
        'data/fs_combined_bs.xml',
        'data/soa_structure_pl_report.xml',
        'data/cash_book_report.xml',
        'data/bank_book_report.xml',
        'data/account_report_action.xml',
        # Wizard
        'wizards/cashflow_report_wizard_views.xml',
        'wizards/sale_cashflow_report_wizard.xml',
        'wizards/budget_combined_report_views.xml',
        'wizards/budget_reforecast_combined_report_views.xml',
        'wizards/profit_and_loss_report_views.xml',
        'wizards/account_payment_wizard_views.xml',
        'wizards/fs_combined_pl_wizard_views.xml',
        'wizards/fs_combined_bs_wizard_views.xml',
        'wizards/profit_and_loss_bu_combined_views.xml',
        'wizards/profit_and_loss_bu_alloc_views.xml',
        'wizards/summary_financial_reports_views.xml',
        'wizards/general_journal_wizard_views.xml',
        'wizards/inventory_report_activities_wizard.xml',
        'wizards/ledger_journal_wizard_views.xml',
        # View
        'views/res_config_settings_views.xml',
        'views/crossovered_budget_views.xml',
        'views/account_report_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/account_cashflow_report_views.xml',
        'views/account_payment_views.xml',
        'views/account_analytic_line_views.xml',
        # Menu
        'menu/menu.xml'
    ],
    'license': 'OEEL-1',
}
