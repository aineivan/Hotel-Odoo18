from odoo import models, fields, api, _
from odoo.fields import Command

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    duration = fields.Integer(string="Duration", required=True, default=1)
    
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'duration')
    def _compute_amount(self):
        for line in self:
            # Default duration
            duration = line.duration or 1.0

            # Compute taxes using Odoo 18 API
            price = line.price_unit * line.product_uom_qty * duration
            taxes = line.tax_id.compute_all(
                price,
                currency=line.currency_id or line.order_id.currency_id,
                quantity=1.0,
                product=line.product_id,
                partner=line.order_id.partner_id
            )

            line.price_subtotal = taxes['total_excluded']
            line.price_tax = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
            line.price_total = taxes['total_included']

    def _prepare_invoice_line(self, **optional_values):
        """Prepare the values to create the invoice line for a sales order line."""
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
