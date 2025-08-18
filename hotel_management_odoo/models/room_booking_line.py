# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: ADARSH K (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
###############################################################################
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class RoomBookingLine(models.Model):
    """Model that handles the room booking form"""
    _name = "room.booking.line"
    _description = "Hotel Folio Line"
    _rec_name = 'room_id'

    @tools.ormcache()
    def _set_default_uom_id(self):
        return self.env.ref('uom.product_uom_day')

    booking_id = fields.Many2one(
        "room.booking",
        string="Booking",
        help="Indicates the Room",
        ondelete="cascade"
    )
    checkin_date = fields.Datetime(
        string="Check In",
        required=True,
        help="You can choose the date, otherwise sets to current Date"
    )
    checkout_date = fields.Datetime(
        string="Check Out",
        required=True,
        help="You can choose the date, otherwise sets to current Date"
    )
    room_id = fields.Many2one(
        'hotel.room',
        string="Room",
        required=True,
        domain="[('status', '=', 'available')]",
        help="Indicates the Room"
    )
    uom_qty = fields.Float(
        string="Duration",
        readonly=True,
        help="The quantity converted into the UoM used by the product"
    )
    uom_id = fields.Many2one(
        'uom.uom',
        default=_set_default_uom_id,
        string="Unit of Measure",
        readonly=True,
        help="This will set the unit of measure used"
    )
    price_unit = fields.Float(
        related='room_id.list_price',
        string='Rent',
        digits='Product Price',
        help="The rent price of the selected room."
    )
    tax_ids = fields.Many2many(
        'account.tax',
        'hotel_room_order_line_taxes_rel',
        'room_id', 'tax_id',
        related='room_id.taxes_ids',
        string='Taxes',
        domain=[('type_tax_use', '=', 'sale')],
        help="Default taxes used when selling the room."
    )
    currency_id = fields.Many2one(
        string='Currency',
        related='booking_id.pricelist_id.currency_id',
        help='The currency used'
    )
    price_subtotal = fields.Float(
        string="Subtotal",
        compute='_compute_price_subtotal',
        store=True,
        help="Total Price excluding Tax"
    )
    price_tax = fields.Float(
        string="Total Tax",
        compute='_compute_price_subtotal',
        store=True,
        help="Tax Amount"
    )
    price_total = fields.Float(
        string="Total",
        compute='_compute_price_subtotal',
        store=True,
        help="Total Price including Tax"
    )
    state = fields.Selection(
        related='booking_id.state',
        string="Order Status",
        copy=False,
        help="Status of the Order"
    )
    booking_line_visible = fields.Boolean(
        default=False,
        string="Booking Line Visible",
        help="If True, then Booking Line will be visible"
    )

    @api.onchange("checkin_date", "checkout_date", "room_id")
    def _onchange_checkin_date(self):
        """Validate booking dates, update duration, and check room availability"""
        if not self.checkin_date or not self.checkout_date:
            return

        # Validate dates
        if self.checkout_date < self.checkin_date:
            raise ValidationError(
                _("Checkout must be greater or equal to checkin date")
            )

        # Compute duration in days
        diffdate = self.checkout_date - self.checkin_date
        qty = diffdate.days
        if diffdate.total_seconds() > 0:
            qty = qty + 1
        self.uom_qty = qty

        # Validate room availability
        if self.room_id:
            existing_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', self.room_id.id),
                ('booking_id.state', 'in', ['reserved', 'check_in']),
                ('id', '!=', self.id if self.id else 0)
            ])
            for existing_line in existing_bookings:
                if (self.checkin_date < existing_line.checkout_date and
                        self.checkout_date > existing_line.checkin_date):
                    raise ValidationError(
                        _("Room '%s' is already booked from %s to %s. "
                          "Please choose different dates or another room.") % (
                              self.room_id.name,
                              existing_line.checkin_date.strftime(
                                  '%Y-%m-%d %H:%M'),
                              existing_line.checkout_date.strftime(
                                  '%Y-%m-%d %H:%M')
                        ))

    @api.depends('uom_qty', 'price_unit', 'tax_ids')
    def _compute_price_subtotal(self):
        """Compute the amounts of the room booking line."""
        for line in self:
            base_line = line._prepare_base_line_for_taxes_computation()
            self.env['account.tax']._add_tax_details_in_base_line(
                base_line, self.env.company
            )
            line.price_subtotal = base_line['tax_details']['raw_total_excluded_currency']
            line.price_total = base_line['tax_details']['raw_total_included_currency']
            line.price_tax = line.price_total - line.price_subtotal
            if (self.env.context.get('import_file', False) and
                    not self.env.user.user_has_groups('account.group_account_manager')):
                line.tax_id.invalidate_recordset(
                    ['invoice_repartition_line_ids']
                )

    def _prepare_base_line_for_taxes_computation(self):
        """Convert the current record to a dictionary in order to use the
        generic taxes computation method defined on account.tax.
        """
        self.ensure_one()
        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            self,
            **{
                'tax_ids': self.tax_ids,
                'quantity': self.uom_qty,
                'partner_id': self.booking_id.partner_id,
                'currency_id': self.currency_id,
            },
        )
