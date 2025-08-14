from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    hotel_book_history_ids = fields.One2many('hotel.book.history', 'sale_order_id', string="Hotel Book History")
    hotel_book_history_count = fields.Integer(string="Hotel Book History Count", compute="_compute_hotel_book_history_count")

    @api.depends('hotel_book_history_ids')
    def _compute_hotel_book_history_count(self):
        for record in self:
            record.hotel_book_history_count = len(record.hotel_book_history_ids)

    def action_view_hotel_book_history(self):
        self.ensure_one()
        action = self.env.ref('ism_hotel.action_hotel_book_history_all').read()[0]
        action['domain'] = [('sale_order_id', '=', self.id)]
        return action

    @api.depends('order_line.price_subtotal', 'order_line.price_tax')
    def _compute_amounts(self):
        super(SaleOrder, self)._compute_amounts()
        for order in self:
            untaxed = sum(line.price_subtotal for line in order.order_line if not line.display_type)
            tax = sum(line.price_tax for line in order.order_line if not line.display_type)
            order.update({
                'amount_untaxed': untaxed,
                'amount_tax': tax,
                'amount_total': untaxed + tax,
            })

    @api.depends('order_line.tax_id', 'order_line.price_unit', 'order_line.duration')
    def _compute_tax_totals(self):
        for order in self:
            tax_totals = {}
            for line in order.order_line:
                if line.display_type:
                    continue
                qty = line.product_uom_qty * line.duration
                taxes = line.tax_id.compute_all(
                    line.price_unit,
                    order.currency_id,
                    qty,
                    product=line.product_id,
                    partner=order.partner_id
                )
                for t in taxes['taxes']:
                    name = t['name']
                    tax_totals[name] = tax_totals.get(name, 0.0) + t['amount']
            order.tax_totals = tax_totals
