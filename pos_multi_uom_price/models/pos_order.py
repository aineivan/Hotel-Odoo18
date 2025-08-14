# -*- coding: utf-8 -*-
# © 2025 ehuerta _at_ ixer.mx
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import logging

from odoo import models, fields, api, _
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)
    
class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    product_uom_id = fields.Many2one('uom.uom', string='Product UoM', related='')
    unit_cost = fields.Float(string='Unit cost', compute='_compute_unit_cost', digits='Product Price')

    @api.model
    def _load_pos_data_fields(self, config_id):
        params = super()._load_pos_data_fields(config_id)
        params += ['product_uom_id']
        return params
    
    @api.depends('price_subtotal', 'total_cost')
    def _compute_margin(self):
        for line in self:
            if line.product_id.type == 'combo':
                line.margin = 0
                line.margin_percent = 0
            else:
                line.margin = line.price_subtotal - line.total_cost * line.product_uom_id.factor_inv
                line.margin_percent = not float_is_zero(line.price_subtotal, precision_rounding=line.currency_id.rounding) and line.margin / line.price_subtotal or 0

    @api.depends('total_cost', 'product_uom_id.factor_inv')
    def _compute_unit_cost(self):
        for line in self:
                line.unit_cost = line.total_cost * line.product_uom_id.factor_inv
