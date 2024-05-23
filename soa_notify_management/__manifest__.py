# -*- coding: utf-8 -*-
{
    'name': 'Notify Management',
    'version': '1.1',
    'summary': 'Notify Management',
    'author': 'Onnet Consulting',
    'sequence': 10,
    'website': 'on.net.vn',
    'category': 'Notify',
    'depends': ['purchase', 'soa_document_code'],
    'data': [
        'data/cron.xml',
        'data/mail_template_data.xml',
    ],
    'auto_install': True,
    'license': 'LGPL-3',
}
