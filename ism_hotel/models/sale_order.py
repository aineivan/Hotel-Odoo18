from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    hotel_book_history_ids = fields.One2many(
        'hotel.book.history',
        'sale_order_id',
        string="Hotel Book History",
    )
    hotel_book_history_count = fields.Integer(
        string="Hotel Book History Count",
        compute="_compute_hotel_book_history_count",
        store=False,
    )

    @api.depends('hotel_book_history_ids')
    def _compute_hotel_book_history_count(self):
        for order in self:
            order.hotel_book_history_count = len(order.hotel_book_history_ids)

    def action_view_hotel_book_history(self):
        self.ensure_one()
        action = self.env.ref('ism_hotel.action_hotel_book_history_all').read()[0]
        action['domain'] = [('sale_order_id', '=', self.id)]
        return action

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total')
    def _compute_amounts(self):
        res = super(SaleOrder, self)._compute_amounts()

        for order in self:
            amount_untaxed = sum(line.price_subtotal or 0.0 for line in order.order_line)
            amount_tax = sum(line.price_tax or 0.0 for line in order.order_line)
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })

        return res

    @api.depends_context('lang')
    @api.depends('order_line.tax_id', 'order_line.price_unit', 'order_line.discount',
                 'order_line.product_uom_qty', 'order_line.duration',
                 'amount_total', 'amount_untaxed', 'currency_id')
    def _compute_tax_totals(self):
        res = super(SaleOrder, self)._compute_tax_totals()

        for order in self:
            order_lines = order.order_line.filtered(lambda l: not l.display_type)
            if not order_lines:
                continue

            tax_base_line_dicts = []
            for line in order_lines:
                duration = getattr(line, 'duration', 1.0) or 1.0
                base_dict = line._convert_to_tax_base_line_dict()
                base_dict['quantity'] = (base_dict.get('quantity') or 0.0) * duration
                tax_base_line_dicts.append(base_dict)

            currency = order.currency_id or order.company_id.currency_id
            try:
                tax_totals = self.env['account.tax']._prepare_tax_totals(tax_base_line_dicts, currency)
                order.tax_totals = tax_totals
            except Exception as e:
                _logger.exception("Failed to compute tax_totals for SO %s: %s", order.name, e)

        return res
