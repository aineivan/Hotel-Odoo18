# -*- coding: utf-8 -*-
from odoo import api, models


class ReportSaleDetails(models.AbstractModel):
    _inherit = "report.point_of_sale.report_saledetails"

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False, **kwargs):
        res = super().get_sale_details(
            date_start=date_start,
            date_stop=date_stop,
            config_ids=config_ids,
            session_ids=session_ids,
            **kwargs,
        )

        sessions = self.env["pos.session"]
        if session_ids:
            sessions = self.env["pos.session"].browse(session_ids)
        elif config_ids:
            date_start = res.get("date_start") or date_start
            date_stop = res.get("date_stop") or date_stop
            configs = self.env["pos.config"].browse(config_ids)
            if date_start and date_stop and configs:
                sessions = self.env["pos.session"].search([
                    ("config_id", "in", configs.ids),
                    ("start_at", ">=", date_start),
                    ("stop_at", "<=", date_stop),
                ])

        invoice_paid_data = []
        invoice_paid_total = 0
        for session in sessions:
            lines = self.env["pos.session.invoice.paid"].sudo().search(
                [("session_id", "=", session.id)],
                order="create_date desc, id desc",
            )
            if not lines:
                continue
            total = sum(lines.mapped("amount"))
            invoice_paid_total += total
            invoice_paid_data.append({
                "session_name": session.name,
                "lines": [
                    {
                        "name": line.invoice_id.name or line.invoice_id.payment_reference or "",
                        "amount": line.amount,
                        "currency": line.currency_id,
                    }
                    for line in lines
                ],
                "total": total,
                "currency": session.currency_id or session.company_id.currency_id,
            })

        res.update({
            "invoice_paid_data": invoice_paid_data,
            "invoice_paid_total": invoice_paid_total,
        })
        return res
