from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import ValidationError

import datetime

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    duration = fields.Integer(string="Duration", required=True, default=1)
    
    # override _compute_amount
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'duration')
    def _compute_amount(self):
        for line in self:
            tax_base_line_dict = line._convert_to_tax_base_line_dict()
            
            # print('before compute taxes : ', tax_base_line_dict)
            tax_base_line_dict['quantity'] *= line.duration
            tax_results = self.env['account.tax']._compute_taxes([tax_base_line_dict])
            # print('after compute taxes : ', tax_results)
            
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })
        
    # override _prepare_invoice_line
    def _prepare_invoice_line(self, **optional_values):
        """Prepare the values to create the new invoice line for a sales order line.

        :param optional_values: any parameter that should be added to the returned invoice line
        :rtype: dict
        """
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