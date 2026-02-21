# -*- coding: utf-8 -*-

{
    "name": "POS Invoice Register Payment",
    "version": "18.0.1.0.5",
    "category": "Point of Sale",
    "summary": "Register invoice payments from inside an open POS session",
    "description": "Pay customer invoices from within the POS session.",
    "author": "Native Innivations Co ltd",
    "company": "Native Innivations Co ltd",
    "maintainer": "Native Innivations Co ltd",
    "website": "https://www.nativeinnivations.com",
    "license": "AGPL-3",
    "depends": ["point_of_sale", "account"],
    "data": [
        "security/ir.model.access.csv",
        "report/pos_invoice_paid_in_report.xml",

    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_invoice_payment/static/src/js/invoicing_button.js",
            "pos_invoice_payment/static/src/js/invoicing_screen.js",
            "pos_invoice_payment/static/src/js/payment_popup.js",
            "pos_invoice_payment/static/src/js/closing_popup_invoice_paid.js",
            "pos_invoice_payment/static/src/xml/numpad_invoicing_button_templates.xml",
            "pos_invoice_payment/static/src/xml/invoice_screen_templates.xml",
            "pos_invoice_payment/static/src/xml/payment_pop_templates.xml",
            "pos_invoice_payment/static/src/xml/closing_popup_invoice_paid.xml",
            "pos_invoice_payment/static/src/css/invoice_list.scss",
        ],
    },
    "images": ["static/description/banner.jpg"],
    "installable": True,
    "application": False,
}
