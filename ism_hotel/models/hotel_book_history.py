from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date

import datetime

class HotelBookHistory(models.Model):
    _name = 'hotel.book.history'
    _description = 'Hotel Book History'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # model get room 
    @api.model
    def default_get_room(self):
        room_id = self.env['hotel.room'].browse(self._context.get('active_room_id'))
        return room_id    

    # field model 
    check_in = fields.Date(string="Check In", required=True)
    check_out = fields.Date(string="Check Out", required=True)
    name = fields.Char(string="Name", required=True, default="New Booking", copy=False, readonly=True)
    duration = fields.Integer(string="Duration", compute='_compute_duration')
    has_sale_order = fields.Boolean(string="Has Sale Order", default=False, compute='_compute_has_sale_order')
    note = fields.Text(string="Notes")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('booked', 'Booked'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('cancelled', 'Cancelled'),
    ], string="State", default='draft', required=True, tracking=True)

    # field constraint 
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    room_ids = fields.Many2many('hotel.room', string="Room", required=True, default=default_get_room)
    history_line_ids = fields.One2many('hotel.book.history.line', 'book_history_id', string="History Line")

    # function define has sale order after checkout
    @api.depends('sale_order_id')
    def _compute_has_sale_order(self):
        for record in self:
            record.has_sale_order = record.state == 'checked_out' and bool(record.sale_order_id)

    # function compute checkdate duration 
    @api.depends('check_in', 'check_out')
    def _compute_duration(self):
        for record in self:
            if record.check_in and record.check_out:
                record.duration = (record.check_out - record.check_in).days
            else:
                record.duration = 0

    # function validate dont chekin if date < today 
    @api.constrains('check_in')
    def _check_booking_date(self):
        for record in self:
            if record.check_in and record.check_in < date.today():
                raise ValidationError("The booking date cannot be in the past.")            
    
    @api.model
    def create(self, vals):
        if vals.get('check_in') and vals.get('check_out'):
            if vals.get('check_in') > vals.get('check_out'):
                raise ValidationError(_("Check In date must be less than Check Out date"))
            
        vals['state'] = 'booked'
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hotel.booking.number') or _('New')
        result = super(HotelBookHistory, self).create(vals)
        
        # sale order id create
        sale_order = self._create_sale_order(result)
        result.sale_order_id = sale_order.id
        
        # get context state if so set state immediately
        if self._context.get('state'):
            result.state = self._context.get('state')

        return result

    @api.onchange('check_in')
    def onchange_check_in(self):
        self._auto_assign_check_out()
        self._check_availability()

    @api.onchange('check_out')
    def onchange_check_out(self):
        self._auto_assign_check_in()
        self._check_availability()

    # action button book 
    def action_book(self):
        for record in self:
            record.state = 'booked'
            for room in record.room_ids:
                room.state = 'booked'

    # action button checkin 
    def action_checkin(self):
        for record in self:
            if date.today() < record.check_in:
                raise ValidationError("It's not time to check in yet")  
            
            record.state = 'checked_in'
        
            # change state of room
            for room in record.room_ids:
                room.state = 'occupied'

            # sale.order to confirm
            if record.sale_order_id.state == 'draft':
                record.sale_order_id.action_confirm()

    # action button checkout 
    def action_checkout(self):
        for record in self:
            record.state = 'checked_out'
            
            # change state of room
            for room in record.room_ids:
                room.state = 'available'

    # action button cancel 
    def action_cancel(self):
        for record in self:
            record.state = 'cancelled'
            
            # change state of room
            for room in record.room_ids:
                room.state = 'available'
                
            # cancel sale order
            record.sale_order_id.action_cancel()
    
    # function create sale order 
    def _create_sale_order(self, result):
        """Create a Sale Order for the booked rooms without using removed Odoo 17 methods."""
        order_lines = []
        room_types = []
        room_type_dict_qty = {}
        room_type_dict_str_join = {}

        # Group rooms by room type
        for room in result.room_ids:
            if room.room_type.id not in room_type_dict_qty:
                room_types.append(room.room_type)
                room_type_dict_qty[room.room_type.id] = 1
                room_type_dict_str_join[room.room_type.id] = [room.name]
            else:
                room_type_dict_qty[room.room_type.id] += 1
                room_type_dict_str_join[room.room_type.id].append(room.name)

        # Join room names for notes
        for rt in room_types:
            names_list = room_type_dict_str_join[rt.id]
            if len(names_list) > 1:
                room_type_dict_str_join[rt.id] = ', '.join(names_list)
            else:
                room_type_dict_str_join[rt.id] = names_list[0]

        # Build sale order lines
        for rt in room_types:
            # Main product line
            order_lines.append((0, 0, {
                'product_id': rt.product_variant_ids[:1].id,  # first variant
                'name': rt.name,
                'product_uom_qty': room_type_dict_qty[rt.id],
                'price_unit': rt.list_price,
                'duration': result.duration,  # optional field if you have custom
            }))
            # Note line (optional, display_type for notes)
            order_lines.append((0, 0, {
                'display_type': 'line_note',
                'name': f"{rt.name} ({room_type_dict_str_join[rt.id]})",
            }))

        # Create sale order safely
        return self.env['sale.order'].create({
            'partner_id': result.partner_id.id,
            'date_order': result.check_in,
            'order_line': order_lines,
        })

    # function cek +- days chekin/checkout            
    def _auto_assign_check_in(self):
        if self.check_out:
            if not self.check_in or (self.check_in and self.check_out < self.check_in):
                self.check_in = self.check_out - datetime.timedelta(days=1)
                
    def _auto_assign_check_out(self):
        if self.check_in:
            if not self.check_out or (self.check_out and self.check_out < self.check_in):
                self.check_out = self.check_in + datetime.timedelta(days=1)

    # function cek availibility            
    def _check_availability(self):
        pass
        self.ensure_one()
        selected_room_ids = self.room_ids
        for room in selected_room_ids:
            is_book_exist = self.env['hotel.book.history'].search([
                ('room_ids', '=', room.id),
                ('check_in', '<=', self.check_in),
                ('check_out', '>=', self.check_in),
                ('state', 'in', ['booked', 'checked_in']),
            ])
            if is_book_exist:
                raise ValidationError(_("Room %s is not available on %s") % (room.name, self.check_in))

    # action view sale order     
    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'name': _('Sale Order'),
            'view_mode': 'form',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }