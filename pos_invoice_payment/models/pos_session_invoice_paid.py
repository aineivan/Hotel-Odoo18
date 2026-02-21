# -*- coding: utf-8 -*-
from odoo import fields, models

class PosSessionInvoicePaid(models.Model):
    _name = "pos.session.invoice.paid"
    _description = "Invoices Paid From POS Session"
    _order = "create_date desc, id desc"

    session_id = fields.Many2one("pos.session", required=True, ondelete="cascade", index=True)
    invoice_id = fields.Many2one("account.move", required=True, ondelete="restrict", index=True)

    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    journal_id = fields.Many2one("account.journal", ondelete="restrict")
    payment_id = fields.Many2one("account.payment", ondelete="set null")  # optional

    company_id = fields.Many2one(related="session_id.company_id", store=True, readonly=True)
