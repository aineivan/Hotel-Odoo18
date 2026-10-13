{
    'name': "KOT opNative",

    'summary': "Adds KOT to POS ,Waiters selection and waiter names in POS orders reports",

    'description': """
Adds KOT to POS ,Waiters selection and waiter names in POS orders reports
    """,

    'author': "Native Innovations Co Ltd",
    'website': "https://nativeinnovationsltd.com",

   
    'category': 'Uncategorized',
    'version': '0.9',

    'depends': ['base', 'point_of_sale', 'hr','pos_restaurant'],
    'assets': {
        'point_of_sale._assets_pos': [
            'native_KOT/static/src/**/*'
        ],
    },

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/is_waiter.xml',
        'views/pos_order_list_waiter.xml',
        # 'views/report_order_waiter.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

