# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Onnet All Companies Activated',
    'category': 'Hidden',
    'version': '1.0',
    'description':
        """
========================

This module edit menu company.
        """,
    'depends': ['web'],
    'auto_install': True,
    'data': [
        "views/webclient_templates.xml"
    ],
    'qweb': [
        "static/src/xml/multi_company.xml",
    ],
}
