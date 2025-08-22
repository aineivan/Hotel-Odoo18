# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class RoomBookingLine(models.Model):
    """Model that handles the room booking form"""
    _name = "room.booking.line"
    _description = "Hotel Folio Line"
    _rec_name = 'room_id'

    @tools.ormcache()
    def _set_default_uom_id(self):
        return self.env.ref('uom.product_uom_day')

    booking_id = fields.Many2one("room.booking", string="Booking",
                                 help="Indicates the Booking",
                                 ondelete="cascade")

    # INHERITED FROM BOOKING: These are computed from booking level
    checkin_date = fields.Datetime(string="Check In",
                                   related='booking_id.checkin_date',
                                   store=True, readonly=True,
                                   help="Check-in date from booking")
    checkout_date = fields.Datetime(string="Check Out",
                                    related='booking_id.checkout_date',
                                    store=True, readonly=True,
                                    help="Check-out date from booking")

    room_id = fields.Many2one('hotel.room', string="Room",
                              help="Select specific room configuration",
                              required=True,
                              domain="[('status', '=', 'available')]")

    # NEW: Physical room identification
    physical_room_code = fields.Char(related='room_id.physical_room_code',
                                     store=True, readonly=True,
                                     string="Physical Room")

    uom_qty = fields.Float(string="Duration",
                           compute='_compute_duration',
                           store=True,
                           help="Duration in days calculated from booking dates")
    uom_id = fields.Many2one('uom.uom',
                             default=_set_default_uom_id,
                             string="Unit of Measure",
                             help="Unit of measure",
                             readonly=True)

    price_unit = fields.Float(related='room_id.list_price',
                              string='Rent per Day',
                              digits='Product Price',
                              help="The rent price per day for the selected room.")

    tax_ids = fields.Many2many('account.tax',
                               'hotel_room_order_line_taxes_rel',
                               'room_id', 'tax_id',
                               related='room_id.taxes_ids',
                               string='Taxes',
                               help="Default taxes used when selling the room.",
                               domain=[('type_tax_use', '=', 'sale')])

    currency_id = fields.Many2one(string='Currency',
                                  related='booking_id.pricelist_id.currency_id',
                                  help='The currency used')

    price_subtotal = fields.Float(string="Subtotal",
                                  compute='_compute_price_subtotal',
                                  help="Total Price excluding Tax",
                                  store=True)
    price_tax = fields.Float(string="Total Tax",
                             compute='_compute_price_subtotal',
                             help="Tax Amount",
                             store=True)
    price_total = fields.Float(string="Total",
                               compute='_compute_price_subtotal',
                               help="Total Price including Tax",
                               store=True)

    state = fields.Selection(related='booking_id.state',
                             string="Order Status",
                             help="Status of the Order",
                             copy=False)

    booking_line_visible = fields.Boolean(default=False,
                                          string="Booking Line Visible",
                                          help="If True, then Booking Line will be visible")

    @api.depends('booking_id.checkin_date', 'booking_id.checkout_date')
    def _compute_duration(self):
        """Compute duration from booking dates"""
        for line in self:
            if line.checkin_date and line.checkout_date:
                delta = line.checkout_date - line.checkin_date
                line.uom_qty = delta.days + (1 if delta.seconds > 0 else 0)
            else:
                line.uom_qty = 0

    @api.depends('uom_qty', 'price_unit', 'tax_ids')
    def _compute_price_subtotal(self):
        """Compute the amounts of the room booking line."""
        for line in self:
            # Skip if essential data is missing
            if not line.currency_id or not line.uom_qty or not line.price_unit:
                line.price_subtotal = 0.0
                line.price_total = 0.0
                line.price_tax = 0.0
                continue

            try:
                # Ensure currency has proper rounding
                if not line.currency_id.rounding or line.currency_id.rounding <= 0:
                    line.currency_id.rounding = 0.01  # Default to 0.01 if invalid

                base_line = line._prepare_base_line_for_taxes_computation()
                self.env['account.tax']._add_tax_details_in_base_line(
                    base_line, self.env.company)

                line.price_subtotal = base_line['tax_details']['raw_total_excluded_currency']
                line.price_total = base_line['tax_details']['raw_total_included_currency']
                line.price_tax = line.price_total - line.price_subtotal

            except Exception as e:
                # Fallback calculation if tax computation fails
                line.price_subtotal = line.price_unit * line.uom_qty
                line.price_tax = 0.0
                line.price_total = line.price_subtotal
                _logger.warning(
                    "Tax computation failed for booking line %s: %s", line.id, str(e))

    def _prepare_base_line_for_taxes_computation(self):
        """Convert the current record to a dictionary for tax computation"""
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



    @api.onchange('room_id')
    def _onchange_room_id(self):
        """When room changes, validate availability and check for duplicates"""
        if not self.room_id:
            return

        # First check for duplicate physical rooms in the same booking
        if self.booking_id and self.booking_id.room_line_ids:
            existing_physical_codes = []
            for line in self.booking_id.room_line_ids:
                if line.id != self.id and line.room_id and line.room_id.physical_room_code:
                    existing_physical_codes.append(line.room_id.physical_room_code)

            if self.room_id.physical_room_code in existing_physical_codes:
                return {
                    'warning': {
                        'title': _('Duplicate Physical Room'),
                        'message': _(
                            "Physical Room '%s' is already selected in this booking!\n\n"
                            "You cannot book the same physical room multiple times with different configurations.\n"
                            "Please choose a different room."
                        ) % self.room_id.physical_room_code
                    }
                }

        # Then check availability if booking dates exist
        if self.room_id and self.booking_id.checkin_date and self.booking_id.checkout_date:
            # Check if this physical room is available for the booking dates
            if not self.room_id.check_room_availability(
                self.booking_id.checkin_date,
                self.booking_id.checkout_date,
                self.booking_id.id
            ):
                # Find conflicting bookings for better error message
                conflicting_bookings = self.env['room.booking.line'].search([
                    ('room_id.physical_room_code', '=',
                    self.room_id.physical_room_code),
                    ('booking_id.state', 'in', ['reserved', 'check_in']),
                    ('checkin_date', '<', self.booking_id.checkout_date),
                    ('checkout_date', '>', self.booking_id.checkin_date),
                    ('booking_id', '!=', self.booking_id.id)
                ])

                conflict_details = []
                for booking in conflicting_bookings:
                    conflict_details.append(
                        f"Booking {booking.booking_id.name} - {booking.room_id.display_name_full} "
                        f"({booking.checkin_date.strftime('%Y-%m-%d')} to "
                        f"{booking.checkout_date.strftime('%Y-%m-%d')})"
                    )

                raise ValidationError(
                    _("Physical room '%s' is not available for the selected dates "
                    "(%s to %s).\n\nConflicting bookings:\n%s\n\n"
                    "Please choose different dates or another room.") % (
                        self.room_id.physical_room_code,
                        self.booking_id.checkin_date.strftime('%Y-%m-%d'),
                        self.booking_id.checkout_date.strftime('%Y-%m-%d'),
                        '\n'.join(conflict_details)
                    ))


    @api.model
    def create(self, vals):
        """Override create to validate no duplicate physical rooms"""
        line = super().create(vals)

        # Check for duplicate physical rooms in the same booking
        if line.room_id and line.booking_id:
            duplicate_lines = line.booking_id.room_line_ids.filtered(
                lambda l: l.id != line.id and
                l.room_id.physical_room_code == line.room_id.physical_room_code
            )

            if duplicate_lines:
                raise ValidationError(
                    _("Physical Room '%s' is already selected in this booking!\n\n"
                    "You cannot book the same physical room multiple times.")
                    % line.room_id.physical_room_code
                )

        # Validate availability after creation
        if line.room_id and line.booking_id.checkin_date and line.booking_id.checkout_date:
            if not line.room_id.check_room_availability(
                line.booking_id.checkin_date,
                line.booking_id.checkout_date,
                line.booking_id.id
            ):
                raise ValidationError(
                    _("Physical room '%s' is not available for the selected dates. "
                    "Please choose different dates or another room.")
                    % line.room_id.physical_room_code
                )

        return line


    def write(self, vals):
        """Override write to validate no duplicate physical rooms when room changes"""
        if 'room_id' in vals:
            for line in self:
                new_room = self.env['hotel.room'].browse(vals['room_id'])
                if new_room and line.booking_id:

                    # Check for duplicates
                    duplicate_lines = line.booking_id.room_line_ids.filtered(
                        lambda l: l.id != line.id and
                        l.room_id.physical_room_code == new_room.physical_room_code
                    )

                    if duplicate_lines:
                        raise ValidationError(
                            _("Physical Room '%s' is already selected in this booking!\n\n"
                            "You cannot book the same physical room multiple times.")
                            % new_room.physical_room_code
                        )

                    # Check availability
                    if (line.booking_id.checkin_date and line.booking_id.checkout_date):
                        if not new_room.check_room_availability(
                            line.booking_id.checkin_date,
                            line.booking_id.checkout_date,
                            line.booking_id.id
                        ):
                            raise ValidationError(
                                _("Physical room '%s' is not available for the selected dates. "
                                "Please choose different dates or another room.")
                                % new_room.physical_room_code
                            )

        return super().write(vals)
