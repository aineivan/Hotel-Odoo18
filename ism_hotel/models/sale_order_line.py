from odoo import models, fields, api
from odoo.fields import Command

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    duration = fields.Integer(string="Duration", required=True, default=1)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'duration')
    def _compute_amount(self):
        for line in self:
            if line.display_type:
                line.update({
                    'price_subtotal': 0.0,
                    'price_tax': 0.0,
                    'price_total': 0.0
                })
                continue

            qty = line.product_uom_qty * (line.duration or 1)
            taxes = line.tax_id.compute_all(
                line.price_unit,
                line.order_id.currency_id,
                qty,
                product=line.product_id,
                partner=line.order_id.partner_id
            )

            amount_untaxed = taxes['total_excluded']
            amount_tax = taxes['total_included'] - amount_untaxed

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = {
            'display_type': self.display_type or 'product',
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'duration': self.duration,
            'price_unit': self.price_unit,
            'tax_ids': [Command.set(self.tax_id.ids)],
            'sale_line_ids': [Command.link(self.id)],
            'is_downpayment': self.is_downpayment,
        }
        analytic_account_id = self.order_id.analytic_account_id.id
        if self.analytic_distribution and not self.display_type:
            res['analytic_distribution'] = self.analytic_distribution
        if analytic_account_id and not self.display_type:
            analytic_account_id = str(analytic_account_id)
            if 'analytic_distribution' in res:
                res['analytic_distribution'][analytic_account_id] = res['analytic_distribution'].get(analytic_account_id, 0) + 100
            else:
                res['analytic_distribution'] = {analytic_account_id: 100}
        if optional_values:
            res.update(optional_values)
        if self.display_type:
            res['account_id'] = False
        return res
