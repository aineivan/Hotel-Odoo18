from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import datetime

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    hotel_book_history_ids = fields.One2many('hotel.book.history', 'sale_order_id', string="Hotel Book History")
    hotel_book_history_count = fields.Integer(string="Hotel Book History Count", compute="_compute_hotel_book_history_count", store=False)
    
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
        # TODO : compute amount_untaxed, amount_tax, amount_total will be counted with duration
        print('compute amounts')
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })
            print('amount_total : ', order.amount_total)
            
        return res
    
    @api.depends_context('lang')
    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'amount_untaxed', 'currency_id')
    def _compute_tax_totals(self):
        res = super(SaleOrder, self)._compute_tax_totals()
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            
            tax_model = self.env['account.tax']

            tax_base_line_dicts = []

            for order_line in order_lines:
                tax_base_line_dict = order_line._convert_to_tax_base_line_dict()
                tax_base_line_dict['quantity'] *= order_line.duration
                tax_base_line_dicts.append(tax_base_line_dict)

            currency_to_use = order.currency_id or order.company_id.currency_id
            tax_totals = tax_model._prepare_tax_totals(tax_base_line_dicts, currency_to_use)
            order.tax_totals = tax_totals

        return res