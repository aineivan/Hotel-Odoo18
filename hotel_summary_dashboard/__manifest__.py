# -*- coding: utf-8 -*-
{
    "name": "Hotel Summary Dashboard",
    "version": "18.0.1.1.0",
    "summary": "Single-page dashboard: Inventory, Purchases, Gross Sales, Bookings",
    "author":"Native Innovations",
    "category": "Hotel/Reporting",
    "license": "LGPL-3",
    "depends": [
        "web",
        "stock_account",
        "purchase",
        "point_of_sale",
        "hr_expense",
        "hotel_management_odoo",
    ],
    "data": [
        # "security/security.xml",
        "security/ir.model.access.csv",
        "views/hotel_dashboard_menu.xml",
        "report/hotel_dashboard_reports.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hotel_summary_dashboard/static/src/css/hotel_dashboard.css",
            "hotel_summary_dashboard/static/src/js/hotel_dashboard.js",
            "hotel_summary_dashboard/static/src/xml/hotel_dashboard.xml",
        ],
    },
    "application": False,
    "installable": True,
}
