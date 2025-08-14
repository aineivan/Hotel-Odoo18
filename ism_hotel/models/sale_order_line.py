from odoo import models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
