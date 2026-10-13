# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import date, datetime


class HotelSummaryDashboardController(http.Controller):

    @http.route("/hotel_summary_dashboard/data", type="jsonrpc", auth="user")
    def hotel_dashboard_data(self, limit=200, date_from=None, date_to=None):
        limit = int(limit or 200)
        env = request.env
        Data = env["hotel.summary.dashboard.data"]

        # ─── Date range ───────────────────────────────────────────────────────
        today = date.today()

        # Plain POS staff (not a POS Manager or system admin) can't browse
        # other dates: always today, regardless of what's passed in --
        # enforced here, not just hidden in the UI, so it can't be bypassed
        # with a crafted request.
        user = env.user
        can_filter = not (
            user.has_group("point_of_sale.group_pos_user")
            and not user.has_group("point_of_sale.group_pos_manager")
            and not user.has_group("base.group_system")
        )

        def parse_date(val, fallback):
            if not val:
                return fallback
            try:
                return datetime.strptime(val, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return fallback

        if can_filter:
            d_from = parse_date(date_from, today)
            d_to   = parse_date(date_to, today)
        else:
            d_from = d_to = today

        # Convert to datetime bounds
        dt_from = datetime.combine(d_from, datetime.min.time())
        dt_to   = datetime.combine(d_to, datetime.max.time())

        # All the heavy lifting lives on hotel.summary.dashboard.data, shared
        # with the PDF report wizard so the two can never drift apart.
        inventory_lines, total_inventory_value = Data.get_inventory_lines(limit=limit)

        purchase_lines, total_purchases_amount = Data.get_purchase_lines(
            dt_from, dt_to, limit=limit)

        sales_lines, sales_by_pos, total_sales, total_cost, gross_profit = \
            Data.get_sales_lines(dt_from, dt_to, limit=limit)

        payment_breakdown_by_pos, payment_method_totals, payment_grand_total = \
            Data.get_sales_payment_breakdown(dt_from, dt_to)

        expense_lines, total_expenses = Data.get_expense_lines(
            d_from, d_to, limit=limit)

        booking_lines, total_paid_amount, room_occupancy, meal_plan_totals = \
            Data.get_booking_lines(dt_from, dt_to, limit=limit)

        active_bookings = env["room.booking"].search_count([
            ("state", "in", ["reserved", "check_in"])
        ])

        return {
            "date_from": str(d_from),
            "date_to":   str(d_to),
            "can_filter": can_filter,
            "cards": {
                "inventory_value":   total_inventory_value,
                "purchase_total":    total_purchases_amount,
                "total_sales":       total_sales,
                "total_cost":        total_cost,
                "gross_profit":      gross_profit,
                "total_expenses":    total_expenses,
                "active_bookings":   active_bookings,
                "total_paid_amount": total_paid_amount,
                "sales_by_pos":      sales_by_pos,
                "payment_breakdown_by_pos": payment_breakdown_by_pos,
                "payment_method_totals":    payment_method_totals,
                "payment_grand_total":      payment_grand_total,
                "room_occupancy":    room_occupancy,
                "meal_plan_totals":  meal_plan_totals,
            },
            "lists": {
                "inventory": inventory_lines,
                "purchases": purchase_lines,
                "sales":     sales_lines,
                "expenses":  expense_lines,
                "bookings":  booking_lines,
            },
        }
