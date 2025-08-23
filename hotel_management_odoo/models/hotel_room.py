# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, UserError


class HotelRoom(models.Model):
    """Model that holds all details regarding hotel room"""
    _name = 'hotel.room'
    _description = 'Rooms'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @tools.ormcache()
    def _get_default_uom_id(self):
        """Method for getting the default uom id"""
        return self.env.ref('uom.product_uom_unit')

    name = fields.Char(string='Room Number', help="Physical Room Number (e.g., 404)",
                       index='trigram', required=True, translate=True)

    # MODIFIED: Physical room code now represents the actual physical room
    physical_room_code = fields.Char(string='Physical Room Code', required=True,
                                     help="Physical room identifier - same for all configurations of the same room (e.g., RM-707)")

    # NEW: Room configuration identifier for unique room records
    room_config_code = fields.Char(string='Room Configuration Code',
                                   help="Unique identifier for this specific room configuration (e.g., RM-707-SGL)")

    status = fields.Selection([("available", "Available"),
                               ("reserved", "Reserved"),
                               ("occupied", "Occupied"),
                               ("unavailable", "Unavailable")],
                              compute='_compute_status',
                              store=True,
                              default="available",
                              string="Status",
                              help="Status of The Room",
                              tracking=True)
    is_unavailable_for_maintenance = fields.Boolean(string="Unavailable for Maintenance",
                                                    tracking=True,
                                                    help="Check this box to make the room unavailable for maintenance.")
    is_room_avail = fields.Boolean(default=True, string="Available",
                                   help="Check if the room is available")
    list_price = fields.Float(string='Rent', digits='Product Price',
                              help="The rent of the room.")
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                             default=_get_default_uom_id, required=True,
                             help="Default unit of measure used for all stock operations.")
    room_image = fields.Image(string="Room Image", max_width=1920,
                              max_height=1920, help='Image of the room')
    taxes_ids = fields.Many2many('account.tax',
                                 'hotel_room_taxes_rel',
                                 'room_id', 'tax_id',
                                 help="Default taxes used when selling the room.",
                                 string='Customer Taxes',
                                 domain=[('type_tax_use', '=', 'sale')],
                                 default=lambda self: self.env.company.account_sale_tax_id)
    room_amenities_ids = fields.Many2many("hotel.amenity",
                                          string="Room Amenities",
                                          help="List of room amenities.")
    floor_id = fields.Many2one('hotel.floor', string='Floor',
                               help="Automatically selects the Floor",
                               tracking=True)
    user_id = fields.Many2one('res.users', string="User",
                              related='floor_id.user_id',
                              help="Automatically selects the manager",
                              tracking=True)
    room_type = fields.Many2one('hotel.room.type', string='Room Type',
                                required=True,
                                help="Select the type of the room.",
                                tracking=True)
    num_person = fields.Integer(string='Number Of Persons',
                                required=True,
                                help="Automatically chooses the No. of Persons",
                                tracking=True)
    description = fields.Html(string='Description', help="Add description",
                              translate=True)

    # NEW: Computed field to show full room name
    display_name_full = fields.Char(
        string='Full Name', compute='_compute_display_name_full', store=True)

    @api.depends('name', 'room_type.name')
    def _compute_display_name_full(self):
        """Compute full display name including room type"""
        for room in self:
            if room.room_type:
                room.display_name_full = f"{room.name} ({room.room_type.name})"
            else:
                room.display_name_full = room.name

    def name_get(self):
        """Override name_get to show room number with type"""
        result = []
        for room in self:
            if room.room_type:
                name = f"{room.name} ({room.room_type.name})"
            else:
                name = room.name
            result.append((room.id, name))
        return result

    @api.constrains("num_person")
    def _check_capacity(self):
        """Check capacity function"""
        for room in self:
            if room.num_person <= 0:
                raise ValidationError(_("Room capacity must be more than 0"))

    @api.onchange("room_type")
    def _onchange_room_type(self):
        """Based on selected room type, number of person will be updated."""
        if self.room_type:
            self.num_person = self.room_type.num_person

    @api.depends('is_unavailable_for_maintenance')
    def _compute_status(self):
        """FIXED: Computes the status of ALL room configurations based on ALL physical room bookings."""
        # First, get ALL currently booked physical rooms across the entire hotel
        all_active_bookings = self.env['room.booking.line'].search([
            ('booking_id.state', 'in', ['reserved', 'check_in']),
            ('checkout_date', '>', fields.Datetime.now())
        ])

        # Get physical room codes of ALL booked rooms
        all_booked_physical_rooms = set()
        booked_configurations = {}  # Track which specific configs are booked and their status

        for booking in all_active_bookings:
            physical_code = booking.room_id.physical_room_code
            all_booked_physical_rooms.add(physical_code)

            # Track the status of each booked configuration
            if booking.room_id.id not in booked_configurations:
                booked_configurations[booking.room_id.id] = booking.booking_id.state

        # Now check each room
        for room in self:
            if room.is_unavailable_for_maintenance:
                room.status = 'unavailable'
                room.is_room_avail = False
                continue

            # Check if this physical room is booked (any configuration)
            if room.physical_room_code in all_booked_physical_rooms:
                # Check if this specific configuration is the one that's booked
                if room.id in booked_configurations:
                    # This specific configuration is booked
                    if booked_configurations[room.id] == 'check_in':
                        room.status = 'occupied'
                    else:
                        room.status = 'reserved'
                else:
                    # Another configuration of this physical room is booked
                    room.status = 'unavailable'

                room.is_room_avail = False
            else:
                # This physical room is not booked at all
                room.status = 'available'
                room.is_room_avail = True
    def check_room_availability(self, checkin_date, checkout_date, exclude_booking_id=None):
        """
        FIXED: Check if this physical room is available for the given date range
        This now properly checks the physical room, not just the configuration
        """
        domain = [
            ('room_id.physical_room_code', '=', self.physical_room_code),
            ('booking_id.state', 'in', ['reserved', 'check_in']),
            ('checkin_date', '<', checkout_date),
            ('checkout_date', '>', checkin_date)
        ]

        if exclude_booking_id:
            domain.append(('booking_id', '!=', exclude_booking_id))

        conflicting_bookings = self.env['room.booking.line'].search(domain)
        return len(conflicting_bookings) == 0

    def action_set_maintenance(self):
        """Set room for maintenance - button action from form view"""
        # Check if the physical room has active bookings
        active_bookings = self.env['room.booking.line'].search([
            ('room_id.physical_room_code', '=', self.physical_room_code),
            ('booking_id.state', 'in', ['reserved', 'check_in']),
            ('checkout_date', '>', fields.Datetime.now())
        ])

        if active_bookings:
            booking_details = []
            for booking in active_bookings:
                booking_details.append(
                    f"Booking {booking.booking_id.name} - Room {booking.room_id.display_name_full} "
                    f"(Check-out: {booking.checkout_date.strftime('%Y-%m-%d %H:%M')})"
                )

            raise UserError(
                _("Cannot set room '%s' for maintenance. "
                  "Active bookings found for physical room %s:\n%s") %
                (self.display_name_full, self.physical_room_code,
                 '\n'.join(booking_details))
            )

        # Set maintenance for ALL room configurations of this physical room
        same_physical_rooms = self.search([
            ('physical_room_code', '=', self.physical_room_code)
        ])
        same_physical_rooms.write({'is_unavailable_for_maintenance': True})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': f"Physical room '{self.physical_room_code}' set for maintenance successfully!",
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_clear_maintenance(self):
        """Clear room maintenance - button action from form view"""
        # Clear maintenance for ALL room configurations of this physical room
        same_physical_rooms = self.search([
            ('physical_room_code', '=', self.physical_room_code)
        ])
        same_physical_rooms.write({'is_unavailable_for_maintenance': False})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': f"Physical room '{self.physical_room_code}' maintenance cleared successfully!",
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model
    def create(self, vals):
        """Override create to auto-generate codes"""
        if not vals.get('physical_room_code') and vals.get('name'):
            vals['physical_room_code'] = self._generate_physical_room_code(
                vals.get('name'))

        if not vals.get('room_config_code') and vals.get('name'):
            vals['room_config_code'] = self._generate_room_config_code(
                vals.get('name'),
                vals.get('room_type')
            )
        return super().create(vals)

    def write(self, vals):
        """Override write to update codes when needed"""
        if ('name' in vals or 'room_type' in vals):
            for room in self:
                new_name = vals.get('name', room.name)
                new_room_type_id = vals.get(
                    'room_type', room.room_type.id if room.room_type else False)

                if 'physical_room_code' not in vals:
                    vals['physical_room_code'] = self._generate_physical_room_code(
                        new_name)

                if 'room_config_code' not in vals:
                    vals['room_config_code'] = self._generate_room_config_code(
                        new_name, new_room_type_id)

        return super().write(vals)

    def _generate_physical_room_code(self, room_name):
        """Generate physical room code based only on the room number (ignore type)."""
        physical_code = f"RM-{room_name}"

        # Ensure uniqueness only if you accidentally reuse same room number twice
        counter = 1
        original_code = physical_code
        while self.env['hotel.room'].search([
            ('physical_room_code', '=', physical_code),
            ('id', '!=', self.id if self.id else False)
        ]):
            physical_code = f"{original_code}-{counter:02d}"
            counter += 1

        return physical_code

    def _generate_room_config_code(self, room_name, room_type_id):
        """Generate room configuration code including room type"""
        if room_type_id:
            room_type = self.env['hotel.room.type'].browse(room_type_id)
            type_code = room_type.name[:3].upper() if room_type.name else 'STD'
        else:
            type_code = 'STD'

        config_code = f"RM-{room_name}-{type_code}"

        # Ensure uniqueness
        counter = 1
        original_code = config_code
        while self.env['hotel.room'].search([
            ('room_config_code', '=', config_code),
            ('id', '!=', self.id if self.id else False)
        ]):
            config_code = f"{original_code}-{counter:02d}"
            counter += 1

        return config_code

    def copy(self, default=None):
        """Override copy to ensure unique codes when duplicating"""
        if default is None:
            default = {}

        if 'physical_room_code' not in default:
            default['physical_room_code'] = False
        if 'room_config_code' not in default:
            default['room_config_code'] = False

        return super().copy(default)

    def refresh_status(self):
        """Method to manually refresh room status - useful for debugging"""
        self._compute_status()
        return True
