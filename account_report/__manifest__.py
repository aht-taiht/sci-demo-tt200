# -*- coding: utf-8 -*-
{
    'name': 'SCI accounting report',
    'category': '',
    'author': 'Tungpd',
    'license': 'LGPL-3',
    'summary': 'SCI report',
    'depends': [
        'account_accountant', 'account_asset', 'onnet_sci_custom_field',
    ],
    'data': [
        'data/account_report_views.xml',
        'security/ir.model.access.csv',
        'wizards/report_revenue_by_product_category_view.xml',
        'wizards/report_allocation_deferred_expenses_view.xml',
        'wizards/report_customer_debt_view.xml',
        'views/account_asset_views.xml',
    ],
    'installable': True,
}
