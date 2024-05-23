# -*- coding: utf-8 -*-
{
    'name' : 'Sales - Customize Sales Commission',
    'version' : '1.2',
    'summary': 'Customize Sales Commission',
    'author': 'Onnet Consulting',
    'sequence': 10,
    'website': 'on.net.vn',
    'description': """Sale Commission,""",
    'category': 'Sales/Sales',
    'depends': ['sale', 'product'],
    'data': [
        'data/crm_tag.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
    ],
    'auto_install': True,
    'license': 'LGPL-3',
}
