# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class RoomBookingLine(models.Model):
    """Room lines for a booking: enforces one configuration per physical room, handles pricing & taxes."""
    _name = "room.booking.line"
    _description = "Hotel Folio Line"
    _rec_name = 'room_id'

    @tools.ormcache()
    def _set_default_uom_id(self):
        return self.env.ref('uom.product_uom_day')

    booking_id = fields.Many2one(
        "room.booking",
        string="Booking",
        help="Parent booking",
        ondelete="cascade",
        required=True,
    )

    # CHANGED: Make these regular datetime fields instead of related fields
    # This allows them to be updated programmatically while still syncing with booking
    checkin_date = fields.Datetime(
        string="Check In",
        help="Check-in date for this room line",
        required=True,
    )
    checkout_date = fields.Datetime(
        string="Check Out",
        help="Check-out date for this room line",
        required=True,
    )

    # Room selection
    room_id = fields.Many2one(
        'hotel.room',
        string="Room",
        required=True,
        help="Select specific room configuration",
        domain="[('status', '=', 'available')]",
    )

    # Physical room identifier (read-only mirror from room)
    physical_room_code = fields.Char(
        related='room_id.physical_room_code',
        store=True, readonly=True,
        string="Physical Room"
    )

    uom_qty = fields.Float(
        string="Duration",
        compute='_compute_duration',
        store=True,
        help="Duration in days calculated from booking dates"
    )
    uom_id = fields.Many2one(
        'uom.uom',
        default=_set_default_uom_id,
        string="Unit of Measure",
        help="Unit of measure",
        readonly=True
    )

    price_unit = fields.Float(
        related='room_id.list_price',
        string='Rent per Day',
        digits='Product Price',
        help="The rent price per day for the selected room."
    )

    tax_ids = fields.Many2many(
        'account.tax',
        'hotel_room_order_line_taxes_rel',
        'room_id', 'tax_id',
        related='room_id.taxes_ids',
        string='Taxes',
        help="Default taxes used when selling the room.",
        domain=[('type_tax_use', '=', 'sale')]
    )

    currency_id = fields.Many2one(
        string='Currency',
        related='booking_id.pricelist_id.currency_id',
        help='The currency used'
    )

    price_subtotal = fields.Float(
        string="Subtotal",
        compute='_compute_price_subtotal',
        help="Total Price excluding Tax",
        store=True
    )
    price_tax = fields.Float(
        string="Total Tax",
        compute='_compute_price_subtotal',
        help="Tax Amount",
        store=True
    )
    price_total = fields.Float(
        string="Total",
        compute='_compute_price_subtotal',
        help="Total Price including Tax",
        store=True
    )

    state = fields.Selection(
        related='booking_id.state',
        string="Order Status",
        help="Status of the Order",
        copy=False
    )

    booking_line_visible = fields.Boolean(
        default=False,
        string="Booking Line Visible",
        help="If True, then Booking Line will be visible"
    )

    # NEW: Add method to sync dates from booking
    @api.model
    def create(self, vals):
        """Auto-sync dates from booking on create if not provided"""
        if 'booking_id' in vals and vals['booking_id']:
            booking = self.env['room.booking'].browse(vals['booking_id'])
            if booking.exists():
                # Only set dates if not already provided
                if 'checkin_date' not in vals or not vals['checkin_date']:
                    vals['checkin_date'] = booking.checkin_date
                if 'checkout_date' not in vals or not vals['checkout_date']:
                    vals['checkout_date'] = booking.checkout_date

        line = super().create(vals)
        line._validate_room_selection()
        return line

    def write(self, vals):
        """Validate on updates."""
        res = super().write(vals)
        if 'room_id' in vals or 'booking_id' in vals:
            for line in self:
                line._validate_room_selection()
        return res

    def _validate_room_selection(self):
        """Centralized validation for room selection"""
        if not self.booking_id or not self.room_id:
            return

        # Duplicate check
        duplicates = self.booking_id.room_line_ids.filtered(
            lambda l: l != self and l.room_id and
            l.room_id.physical_room_code == self.room_id.physical_room_code
        )
        if duplicates:
            raise ValidationError(
                _("Physical Room '%s' is already selected in this booking!\n\n"
                  "You cannot book the same physical room multiple times with different configurations.")
                % self.room_id.physical_room_code
            )

        # Availability check
        if self.checkin_date and self.checkout_date:
            if not self.room_id.check_room_availability(
                self.checkin_date,
                self.checkout_date,
                self.booking_id.id
            ):
                # Build detailed conflict message
                conflicting = self.env['room.booking.line'].search([
                    ('room_id.physical_room_code', '=',
                     self.room_id.physical_room_code),
                    ('booking_id.state', 'in', ['reserved', 'check_in']),
                    ('checkin_date', '<', self.checkout_date),
                    ('checkout_date', '>', self.checkin_date),
                    ('booking_id', '!=', self.booking_id.id),
                ])

                details = []
                for conflict in conflicting:
                    try:
                        details.append(
                            f"Booking {conflict.booking_id.name} - {getattr(conflict.room_id, 'display_name_full', conflict.room_id.display_name)} "
                            f"({conflict.checkin_date.strftime('%Y-%m-%d')} to {conflict.checkout_date.strftime('%Y-%m-%d')})"
                        )
                    except Exception:
                        details.append(
                            f"Booking {conflict.booking_id.name} ({conflict.checkin_date} to {conflict.checkout_date})"
                        )

                raise ValidationError(
                    _("Physical room '%s' is not available for the selected dates "
                      "(%s to %s).\n\nConflicting bookings:\n%s\n\n"
                      "Please choose different dates or another room.") % (
                        self.room_id.physical_room_code,
                        self.checkin_date.strftime('%Y-%m-%d'),
                        self.checkout_date.strftime('%Y-%m-%d'),
                        '\n'.join(details) if details else _(
                            'Unknown conflicts')
                    )
                )

    @api.depends('checkin_date', 'checkout_date')
    def _compute_duration(self):
        """Compute duration from line's own dates."""
        for line in self:
            if line.checkin_date and line.checkout_date:
                delta = line.checkout_date - line.checkin_date
                # Count an extra day if there's any seconds (cross-day time)
                line.uom_qty = delta.days + (1 if delta.seconds > 0 else 0)
            else:
                line.uom_qty = 0

    @api.depends('uom_qty', 'price_unit', 'tax_ids')
    def _compute_price_subtotal(self):
        """Compute amounts using account.tax engine; fallback to simple multiply on failure."""
        for line in self:
            if not line.currency_id or not line.uom_qty or not line.price_unit:
                line.price_subtotal = 0.0
                line.price_total = 0.0
                line.price_tax = 0.0
                continue

            try:
                # Ensure currency rounding sane
                if not line.currency_id.rounding or line.currency_id.rounding <= 0:
                    line.currency_id.rounding = 0.01

                base_line = line._prepare_base_line_for_taxes_computation()
                self.env['account.tax']._add_tax_details_in_base_line(
                    base_line, self.env.company
                )

                line.price_subtotal = base_line['tax_details']['raw_total_excluded_currency']
                line.price_total = base_line['tax_details']['raw_total_included_currency']
                line.price_tax = line.price_total - line.price_subtotal

            except Exception as e:
                line.price_subtotal = line.price_unit * line.uom_qty
                line.price_tax = 0.0
                line.price_total = line.price_subtotal
                _logger.warning(
                    "Tax computation failed for booking line %s: %s", line.id, str(e))

    def _prepare_base_line_for_taxes_computation(self):
        """Prepare dict for account.tax computation API."""
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

    @api.onchange('booking_id', 'room_id')
    def _onchange_booking_id_room_id(self):
        """
        Dynamic domain and date sync:
          - Hide any room whose physical_room_code is already selected in this booking (excluding self).
          - Sync dates from booking if they exist
          - Keep base availability status filter.
        """
        # Sync dates from booking
        if self.booking_id:
            if self.booking_id.checkin_date and not self.checkin_date:
                self.checkin_date = self.booking_id.checkin_date
            if self.booking_id.checkout_date and not self.checkout_date:
                self.checkout_date = self.booking_id.checkout_date

        # Dynamic domain
        domain = [('status', '=', 'available')]
        if self.booking_id:
            taken_physical_codes = [
                l.room_id.physical_room_code
                for l in self.booking_id.room_line_ids
                if l.room_id and l != self
            ]
            if taken_physical_codes:
                domain.append(
                    ('physical_room_code', 'not in', taken_physical_codes))

        res = {'domain': {'room_id': domain}}

        # Inline validation warnings (non-blocking)
        if self.room_id:
            # Duplicate check
            if self.booking_id:
                existing_same_physical = self.booking_id.room_line_ids.filtered(
                    lambda l: l != self and l.room_id and
                    l.room_id.physical_room_code == self.room_id.physical_room_code
                )
                if existing_same_physical:
                    res['warning'] = {
                        'title': _('Duplicate Physical Room'),
                        'message': _(
                            "Physical Room '%s' is already selected in this booking!\n\n"
                            "You cannot book the same physical room multiple times with different configurations."
                        ) % self.room_id.physical_room_code
                    }
                    return res

        return res

    @api.onchange('room_id')
    def _onchange_room_id(self):
        """Validate room selection when room changes."""
        if not self.room_id or not self.booking_id:
            return

        # Check for duplicates (non-blocking warning)
        duplicates = self.booking_id.room_line_ids.filtered(
            lambda l: l != self and l.room_id and
            l.room_id.physical_room_code == self.room_id.physical_room_code
        )
        if duplicates:
            return {
                'warning': {
                    'title': _('Duplicate Physical Room'),
                    'message': _(
                        "Physical Room '%s' is already selected in this booking!\n\n"
                        "You cannot book the same physical room multiple times with different configurations."
                    ) % self.room_id.physical_room_code
                }
            }

    @api.constrains('room_id', 'booking_id')
    def _constrain_unique_physical_room_per_booking(self):
        """Hard constraint: only one configuration per physical room per booking."""
        for line in self:
            if line.booking_id and line.room_id:
                duplicates = line.booking_id.room_line_ids.filtered(
                    lambda l: l != line and l.room_id and
                    l.room_id.physical_room_code == line.room_id.physical_room_code
                )
                if duplicates:
                    raise ValidationError(
                        _("You cannot book multiple configurations of the same physical room (%s).")
                        % line.room_id.physical_room_code
                    )

    # NEW: Method to sync dates from booking (called from booking model)
    def sync_dates_from_booking(self):
        """Sync checkin/checkout dates from parent booking"""
        for line in self:
            if line.booking_id:
                line.write({
                    'checkin_date': line.booking_id.checkin_date,
                    'checkout_date': line.booking_id.checkout_date,
                })
