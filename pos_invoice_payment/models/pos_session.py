# -*- coding: utf-8 -*-
from odoo import api, fields, models

class PosSession(models.Model):
    _inherit = "pos.session"

    invoice_paid_line_ids = fields.One2many(
        "pos.session.invoice.paid",
        "session_id",
        string="Invoices Paid (POS)",
        readonly=True,
    )

    invoice_paid_total = fields.Monetary(
        string="Invoices Paid Total",
        compute="_compute_invoice_paid_total",
        currency_field="currency_id",
        readonly=True,
    )

    @api.depends("invoice_paid_line_ids.amount")
    def _compute_invoice_paid_total(self):
        for session in self:
            session.invoice_paid_total = sum(session.invoice_paid_line_ids.mapped("amount"))

    def get_closing_control_data(self):
        res = super().get_closing_control_data()
        self.ensure_one()
        lines = self.env["pos.session.invoice.paid"].sudo().search(
            [("session_id", "=", self.id)],
            order="create_date desc, id desc",
        )
        res.update({
            "invoice_paid_lines": [
                {
                    "id": line.id,
                    "name": line.invoice_id.name or line.invoice_id.payment_reference or "",
                    "amount": line.amount,
                }
                for line in lines
            ],
            "invoice_paid_total": sum(lines.mapped("amount")),
        })
        return res
