from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    hotel_book_history_ids = fields.One2many(
        'hotel.book.history', 'sale_order_id', string="Hotel Book History"
    )
    hotel_book_history_count = fields.Integer(
        string="Hotel Book History Count",
        compute="_compute_hotel_book_history_count",
        store=False
    )

    @api.depends('hotel_book_history_ids')
    def _compute_hotel_book_history_count(self):
        for record in self:
            record.hotel_book_history_count = len(record.hotel_book_history_ids)

    def action_view_hotel_book_history(self):
        self.ensure_one()
        action = self.env.ref('ism_hotel.action_hotel_book_history_all').read()[0]
        action['domain'] = [('sale_order_id', '=', self.id)]
        return action

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total')
    def _compute_amounts(self):
        res = super(SaleOrder, self)._compute_amounts()
        for order in self:
            amount_untaxed = sum(line.price_subtotal for line in order.order_line)
            amount_tax = sum(line.price_tax for line in order.order_line)
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })
        return res

    @api.depends_context('lang')
    @api.depends('order_line.tax_id', 'order_line.price_unit', 'order_line.discount',
                 'order_line.product_uom_qty', 'order_line.duration')
    def _compute_tax_totals(self):
        res = super(SaleOrder, self)._compute_tax_totals()
        for order in self:
            order_lines = order.order_line.filtered(lambda l: not l.display_type)
            if not order_lines:
                continue

            currency = order.currency_id or order.company_id.currency_id
            tax_totals = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }

            for line in order_lines:
                duration = line.duration or 1.0
                price = line.price_unit * line.product_uom_qty * duration
                taxes = line.tax_id.compute_all(
                    price,
                    currency=currency,
                    quantity=1.0,
                    product=line.product_id,
                    partner=order.partner_id
                )
                tax_totals['amount_untaxed'] += taxes['total_excluded']
                tax_totals['amount_tax'] += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))

            tax_totals['amount_total'] = tax_totals['amount_untaxed'] + tax_totals['amount_tax']
            order.tax_totals = tax_totals

        return res
