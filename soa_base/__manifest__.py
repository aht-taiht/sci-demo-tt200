# -*- coding: utf-8 -*-
{
    'name': 'SOA - Inventory',
    'version': '1.2',
    'summary': 'SOA Inventory',
    'author': 'Onnet Consulting',
    'sequence': 10,
    'website': 'on.net.vn',
    'description': """Customize Inventory""",
    'category': 'Inventory/Inventory',
    'depends': ['stock', 'product', 'analytic'],
    'data': [
        'security/analytic_account_rule.xml',
        'views/product_template_views.xml',
        'views/stock_package_type_views.xml',
        'views/account_move_views.xml'
    ],
    "assets": {
        "web.assets_backend": [
            "soa_base/static/src/scss/soa.scss",
        ],
    },
    'auto_install': True,
    'license': 'LGPL-3',
}
