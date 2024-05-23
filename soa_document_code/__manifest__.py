# -*- coding: utf-8 -*-
{
    'name': 'SOA - Document Code',
    'version': '1.0',
    'summary': 'SOA - Document Code',
    'author': 'Onnet Consulting',
    'sequence': 10,
    'website': 'on.net.vn',
    'description': """Customization for Document Code""",
    'category': 'Inventory/Inventory',
    'depends': ['base', 'sale', 'project', 'purchase',
        'account', 'sale_project', 'soa_purchase_management', 'soa_sale_management'
                ],
    'data': [
        'security/ir.model.access.csv',
        # Views
        'views/project_project_views.xml',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/product_category_views.xml',
        # Data
        'data/sale_order_sequence.xml',
        'data/project_project_sequence.xml',
        'data/purchase_order_sequence.xml',
    ],
    'auto_install': False,
    'license': 'LGPL-3',
}
