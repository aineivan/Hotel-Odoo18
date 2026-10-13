# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import _, fields, models
from odoo.exceptions import ValidationError

# A PDF should cover the whole period, not just the first page the
# on-screen dashboard happens to be showing.
REPORT_ROW_LIMIT = 10000


class HotelSummaryDashboardReport(models.TransientModel):
    """Lets a tab of the hotel summary dashboard be downloaded as a PDF,
    using the exact same aggregation logic (hotel.summary.dashboard.data)
    as the live dashboard, for the same date range."""
    _name = "hotel.summary.dashboard.report"
    _description = "Hotel Summary Dashboard Report"

    report_type = fields.Selection([
        ("inventory", "Inventory"),
        ("purchases", "Purchases"),
        ("sales", "Sales Summary"),
        ("expenses", "Expenses"),
        ("bookings", "Bookings"),
    ], string="Report", required=True, default="sales")
    date_from = fields.Date(string="From", required=True,
                            default=fields.Date.context_today)
    date_to = fields.Date(string="To", required=True,
                          default=fields.Date.context_today)
    company_id = fields.Many2one("res.company", string="Company",
                                 default=lambda self: self.env.company)

    def _get_data(self):
        """Fetch this report's rows via the shared aggregation model."""
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_("'From' must be on or before 'To'."))

        Data = self.env["hotel.summary.dashboard.data"]
        dt_from = datetime.combine(self.date_from, datetime.min.time())
        dt_to = datetime.combine(self.date_to, datetime.max.time())

        if self.report_type == "inventory":
            lines, total = Data.get_inventory_lines(limit=REPORT_ROW_LIMIT)
            return {"lines": lines, "total": total}
        if self.report_type == "purchases":
            lines, total = Data.get_purchase_lines(
                dt_from, dt_to, limit=REPORT_ROW_LIMIT)
            return {"lines": lines, "total": total}
        if self.report_type == "sales":
            lines, sales_by_pos, total_sales, _total_cost, _gross_profit = \
                Data.get_sales_lines(dt_from, dt_to, limit=REPORT_ROW_LIMIT)
            payment_breakdown_by_pos, payment_method_totals, payment_grand_total = \
                Data.get_sales_payment_breakdown(dt_from, dt_to)
            return {"lines": lines, "sales_by_pos": sales_by_pos,
                    "total_sales": total_sales,
                    "payment_breakdown_by_pos": payment_breakdown_by_pos,
                    "payment_method_totals": payment_method_totals,
                    "payment_grand_total": payment_grand_total}
        if self.report_type == "expenses":
            lines, total = Data.get_expense_lines(
                self.date_from, self.date_to, limit=REPORT_ROW_LIMIT)
            return {"lines": lines, "total": total}
        # bookings
        lines, total_paid_amount, room_occupancy = \
            Data.get_booking_lines(dt_from, dt_to, limit=REPORT_ROW_LIMIT)
        return {"lines": lines, "total_paid_amount": total_paid_amount,
                "room_occupancy": room_occupancy}

    def _period_label(self):
        self.ensure_one()
        if self.date_from == self.date_to:
            return self.date_from.strftime("%d %b %Y")
        return "%s - %s" % (self.date_from.strftime("%d %b %Y"),
                            self.date_to.strftime("%d %b %Y"))

    def action_download_pdf(self):
        return self.env.ref(
            "hotel_summary_dashboard.action_report_hotel_dashboard"
        ).report_action(self)
