# -*- coding: utf-8 -*-
{
    'name': "Purchase Indonesia Product Category",

    'summary': """
        One Purchase Request one Product Category""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Mahroza",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Purchase',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','purchase_indonesia'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/inherit_purchase_request.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo.xml',
    ],
}