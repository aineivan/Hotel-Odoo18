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
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import fields, models


class HotelRoomType(models.Model):
    """Model for managing different types of hotel rooms."""
    _name = 'hotel.room.type'
    _description = 'Hotel Room Type'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True,
                       help="e.g. Single, Double, Suite")
    num_person = fields.Integer(string='Capacity', required=True, default=1,
                                help="The maximum number of persons for this room type.")

