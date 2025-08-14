# -*- coding: utf-8 -*-
# © 2025 ehuerta _at_ ixer.mx
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import models, fields, api, _


class prod_tmpl_multi_uom(models.Model):
    _name = 'product.tmpl.multi.uom.price'
    _description = 'Product template multiple uom price'

    product_tmpl_id = fields.Many2one(
        'product.template',
        'Product Template',
        required=True,
        ondelete="cascade",
        readonly=True
    )
    category_id = fields.Many2one(related='product_tmpl_id.uom_id.category_id', readonly=True )
    uom_id = fields.Many2one('uom.uom',
        string="Unit of Measure",
        domain="[('category_id', '=', category_id)]",
        required=True
    )
    price = fields.Float('Price',
        required=True,
        digits='Product Price'
    )


    def _sync_price_to_variants(self):
        ProductMultiUom = self.env['product.multi.uom.price']
        variant_uom_keys = []
        existing_prices_map = {}
        for rec in self:
            for variant in rec.product_tmpl_id.product_variant_ids:
                key = (variant.id, rec.uom_id.id)
                variant_uom_keys.append(key)
        if variant_uom_keys:
            existing_prices = ProductMultiUom.search([
                ('product_id', 'in', [v_id for v_id, _ in variant_uom_keys]),
                ('uom_id', 'in', [u_id for _, u_id in variant_uom_keys])
            ])
            for price in existing_prices:
                existing_prices_map[(price.product_id.id, price.uom_id.id)] = price
        to_create = []
        for rec in self:
            for variant in rec.product_tmpl_id.product_variant_ids:
                key = (variant.id, rec.uom_id.id)
                existing = existing_prices_map.get(key)
                if existing:
                    if existing.price != rec.price:
                        existing.price = rec.price
                else:
                    to_create.append({
                        'product_id': variant.id,
                        'uom_id': rec.uom_id.id,
                        'price': rec.price,
                    })
        if to_create:
            ProductMultiUom.create(to_create)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_price_to_variants()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_price_to_variants()
        return res

    _sql_constraints = [
        ('product_tmpl_uom_uniq',
         'UNIQUE(product_tmpl_id, uom_id)',
         'Each Unit of Measure must be unique per product template.')
    ]


class prod_multi_uom(models.Model):
    _name = 'product.multi.uom.price'
    _inherit = ['pos.load.mixin']
    _description = 'Product variant multiple uom price'

    product_id = fields.Many2one(
        'product.product',
        'Product variant',
        required=True,
        ondelete="cascade",
        readonly=True
    )
    category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True )
    uom_id = fields.Many2one('uom.uom',
        string="Unit of Measure",
        domain="[('category_id', '=', category_id)]",
        required=True
    )
    price = fields.Float('Price',
        required=True,
        digits='Product Price'
    )



    @api.model
    def _load_pos_self_data_fields(self, config_id):
        return ['id', 'product_id', 'uom_id', 'price']

    @api.model
    def _load_pos_self_data_domain(self, data):
        return self._load_pos_data_domain(data)
    
    def _load_pos_data(self, data):
        domain = self._load_pos_self_data_domain(data)
        fields = self._load_pos_self_data_fields(data['pos.config']['data'][0]['id'])
        return {
            'data': self.search_read(domain, fields, load=False),
            'fields': fields,
        }
    
    _sql_constraints = [
        ('product_variant_uom_uniq',
         'UNIQUE(product_id, uom_id)',
         'Each Unit of Measure must be unique per product variant.')
    ]
