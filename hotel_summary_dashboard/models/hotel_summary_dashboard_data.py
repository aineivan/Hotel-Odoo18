# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, models

# Orders paid (at least partly) via this payment method are comps / give-
# aways: they still show up in every breakdown (by product, by point of
# sale, by payment method), but are excluded from the "Total Sales"
# headline figure so comped revenue doesn't inflate it.
NON_REVENUE_PAYMENT_METHODS = {'complementary'}


class HotelSummaryDashboardData(models.AbstractModel):
    """Shared data-aggregation logic for the hotel summary dashboard.

    Used by both the JSON controller (the live dashboard) and the PDF
    report wizard, so the numbers on screen and the numbers on a
    downloaded PDF can never drift apart.
    """
    _name = 'hotel.summary.dashboard.data'
    _description = 'Hotel Summary Dashboard Data'

    def get_inventory_lines(self, limit=200):
        """Real-time stock snapshot: (lines, total_inventory_value)."""
        products = self.env['product.product'].search([
            ('is_storable', '=', True),
        ], limit=limit)

        lines = []
        total_inventory_value = 0.0
        for p in products:
            total_inventory_value += p.total_value
            lines.append({
                'product_id':    p.id,
                'product':       p.display_name,
                'unit_cost':     p.standard_price,
                'qty_available': p.qty_available,
                'total_value':   p.total_value,
            })
        return lines, total_inventory_value

    def get_purchase_lines(self, dt_from, dt_to, limit=200):
        """Confirmed purchase order lines in range: (lines, total_amount)."""
        purchase_orders = self.env['purchase.order'].search([
            ('state', '=', 'purchase'),
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
        ])
        if purchase_orders:
            polines = self.env['purchase.order.line'].search([
                ('order_id', 'in', purchase_orders.ids),
                ('state', '=', 'purchase'),
            ], order='create_date desc', limit=limit)
        else:
            polines = self.env['purchase.order.line'].browse([])

        lines = []
        total_purchases_amount = 0.0
        for line in polines:
            subtotal = line.price_subtotal
            total_purchases_amount += subtotal
            lines.append({
                'purchase_line_id':  line.id,
                'product_id':        line.product_id.id,
                'product':           line.product_id.display_name,
                'qty':               line.product_qty,
                'unit_price':        line.price_unit,
                'subtotal':          subtotal,
                'vendor':            line.order_id.partner_id.name,
                'date':              line.order_id.date_order,
                'purchase_order_id': line.order_id.id,
            })
        return lines, total_purchases_amount

    def get_sales_lines(self, dt_from, dt_to, limit=200):
        """POS sales grouped by product and by point of sale.

        Returns (sales_lines, sales_by_pos, total_sales, total_cost,
        gross_profit).
        """
        pos_lines = self.env['pos.order.line'].search([
            ('order_id.state', 'in', ['paid', 'done']),
            ('order_id.date_order', '>=', dt_from),
            ('order_id.date_order', '<=', dt_to),
        ])

        # Orders settled (at least partly) via a non-revenue payment method
        # (e.g. "Complementary"): their lines stay in every breakdown below,
        # but don't count towards the Total Sales headline figure.
        orders = pos_lines.mapped('order_id')
        non_revenue_order_ids = set()
        if orders:
            comp_payments = self.env['pos.payment'].search([
                ('pos_order_id', 'in', orders.ids),
            ])
            non_revenue_order_ids = {
                p.pos_order_id.id for p in comp_payments
                if (p.payment_method_id.name or '').strip().lower()
                in NON_REVENUE_PAYMENT_METHODS
            }

        product_sales = defaultdict(lambda: {
            'product_id': None, 'product': '', 'category': '',
            'qty_sold': 0.0, 'revenue': 0.0, 'cost': 0.0, 'profit': 0.0,
        })
        pos_sales = defaultdict(lambda: {'pos_id': None, 'pos': '', 'amount': 0.0})

        total_sales = 0.0
        total_cost  = 0.0

        for line in pos_lines:
            product_id = line.product_id.id
            sales_subtotal = line.price_subtotal_incl

            if hasattr(line, 'total_cost') and line.total_cost:
                cost = line.total_cost
            else:
                cost = line.product_id.standard_price * line.qty

            product_sales[product_id]['product_id'] = product_id
            product_sales[product_id]['product'] = line.product_id.display_name
            product_sales[product_id]['category'] = line.product_id.categ_id.name or ''
            product_sales[product_id]['qty_sold'] += line.qty
            product_sales[product_id]['revenue'] += sales_subtotal
            product_sales[product_id]['cost'] += cost
            product_sales[product_id]['profit'] += (sales_subtotal - cost)

            config = line.order_id.config_id
            pos_sales[config.id]['pos_id'] = config.id
            pos_sales[config.id]['pos'] = config.name or ''
            pos_sales[config.id]['amount'] += sales_subtotal

            # Total Sales headline: skip lines on comp/giveaway orders.
            if line.order_id.id not in non_revenue_order_ids:
                total_sales += sales_subtotal
            total_cost += cost

        sales_lines = sorted(product_sales.values(), key=lambda x: x['product'])
        sales_by_pos = sorted(pos_sales.values(), key=lambda x: x['amount'], reverse=True)
        gross_profit = total_sales - total_cost

        return sales_lines, sales_by_pos, total_sales, total_cost, gross_profit

    def get_sales_payment_breakdown(self, dt_from, dt_to):
        """Amount collected per payment method, broken down by point of
        sale, for paid/done orders in range.

        Returns (pos_rows, method_totals, grand_total) where:
        - pos_rows: list of {pos_id, pos, methods: [{method, amount}],
          total} -- one entry per point of sale, methods sorted by name.
        - method_totals: list of {method, amount} -- grand total per
          payment method, across every point of sale.
        - grand_total: float.
        """
        payments = self.env['pos.payment'].search([
            ('pos_order_id.state', 'in', ['paid', 'done']),
            ('pos_order_id.date_order', '>=', dt_from),
            ('pos_order_id.date_order', '<=', dt_to),
        ])

        # pos_id -> method_id -> amount
        breakdown = defaultdict(lambda: defaultdict(float))
        pos_names = {}
        method_names = {}
        pos_totals = defaultdict(float)
        method_totals_map = defaultdict(float)
        grand_total = 0.0

        for payment in payments:
            config = payment.pos_order_id.config_id
            method = payment.payment_method_id
            amount = payment.amount

            breakdown[config.id][method.id] += amount
            pos_names[config.id] = config.name or ''
            method_names[method.id] = method.name or ''
            pos_totals[config.id] += amount
            method_totals_map[method.id] += amount
            grand_total += amount

        pos_rows = []
        for pos_id in sorted(breakdown, key=lambda pid: pos_names.get(pid, '')):
            methods = [
                {'method': method_names[mid], 'amount': amount}
                for mid, amount in sorted(
                    breakdown[pos_id].items(),
                    key=lambda kv: method_names[kv[0]])
            ]
            pos_rows.append({
                'pos_id': pos_id,
                'pos': pos_names[pos_id],
                'methods': methods,
                'total': pos_totals[pos_id],
            })

        method_totals = [
            {'method': method_names[mid], 'amount': amount}
            for mid, amount in sorted(
                method_totals_map.items(), key=lambda kv: method_names[kv[0]])
        ]

        return pos_rows, method_totals, grand_total

    def get_expense_lines(self, d_from, d_to, limit=200):
        """HR expenses in range: (lines, total_expenses)."""
        expenses = self.env['hr.expense'].search([
            ('date', '>=', d_from),
            ('date', '<=', d_to),
        ], order='date desc', limit=limit)

        lines = []
        total_expenses = 0.0
        for expense in expenses:
            amount = expense.total_amount or 0.0
            total_expenses += amount
            lines.append({
                'expense_id':  expense.id,
                'employee':    expense.employee_id.sudo().name or '',
                'category':    expense.product_id.name if expense.product_id else '',
                'description': expense.name or '',
                'date':        expense.date,
                'amount':      amount,
                'state':       expense.state,
            })
        return lines, total_expenses

    def get_booking_lines(self, dt_from, dt_to, limit=200):
        """Room bookings in range: (lines, total_paid_amount, occupancy,
        meal_plan_totals)."""
        bookings = self.env['room.booking'].search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
        ], order='date_order desc', limit=limit)

        lines = []
        for booking in bookings:
            rooms = ', '.join(booking.room_line_ids.mapped('room_id.name'))

            # Same day-count convention as room.booking.line's own
            # checkin/checkout onchange, applied at the booking level.
            no_of_days = 0
            if booking.checkin_date and booking.checkout_date:
                diffdate = booking.checkout_date - booking.checkin_date
                no_of_days = diffdate.days
                if diffdate.total_seconds() > 0:
                    no_of_days += 1

            # Combined nightly rate across every room on this booking.
            rate = sum(booking.room_line_ids.mapped('price_unit'))

            lines.append({
                'booking_id':    booking.id,
                'room':          rooms,
                'customer':      booking.partner_id.name,
                'checkin_date':  booking.checkin_date,
                'checkout_date': booking.checkout_date,
                'no_of_days':    no_of_days,
                'rate':          rate,
                'total_amount':  booking.amount_total,
                'state':         booking.state,
            })

        total_paid_amount = sum(bookings.mapped('invoice_amount_paid'))

        # Room occupancy is a real-time physical status, not tied to the
        # selected date range -- it answers "right now", same as Stock
        # Value elsewhere in this dashboard.
        total_rooms = self.env['hotel.room'].search_count([])
        occupied_rooms = self.env['hotel.room'].search_count(
            [('status', '=', 'occupied')])
        occupancy = {
            'occupied': occupied_rooms,
            'unoccupied': total_rooms - occupied_rooms,
            'total_rooms': total_rooms,
        }

        # Meal plan breakdown for the bookings in this period.
        meal_plan_labels = dict(
            bookings._fields['meal_plan']._description_selection(self.env))
        meal_plan_counts = defaultdict(int)
        for booking in bookings:
            label = meal_plan_labels.get(booking.meal_plan) or _('Not Set')
            meal_plan_counts[label] += 1
        meal_plan_totals = [
            {'meal_plan': label, 'count': meal_plan_counts[label]}
            for label in sorted(meal_plan_counts)
        ]

        return lines, total_paid_amount, occupancy, meal_plan_totals
