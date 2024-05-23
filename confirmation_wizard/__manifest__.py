# -*- coding: utf-8 -*-
{
    'name': 'Confirmation Wizard',
    'version': '1.0',
    'summary': 'Web',
    'author': 'Onnet Consulting',
    'sequence': 10,
    'website': 'on.net.vn',
    'description': """Confirmation Wizard""",
    'category': 'Web',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/confirm_wizard_views.xml',
    ],
    'auto_install': True,
    'license': 'LGPL-3',
}
