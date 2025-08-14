from odoo import models, fields, api, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # field model 
    is_room = fields.Boolean(string="Is room", help="Check if this product is a hotel's room type")
    max_allowed_person = fields.Integer(string="Max allowed person", default=1)

    # field constraint 
    amenity_line_ids = fields.One2many('hotel.amenity.line', 'product_id', string="Amenities")
    room_ids = fields.One2many('hotel.room', 'room_type', string="Rooms")