from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def get_invoices(self):
        """Return customer invoices for POS invoice payment screen."""
        invoices = self.search([
            ("move_type", "=", "out_invoice"),
            ("state", "in", ("draft", "posted")),
            ("payment_state", "!=", "paid"),
        ], order="invoice_date desc, id desc")

        return [{
            "invoice_id": inv.id,
            "name": inv.name,
            "payment_reference": inv.payment_reference,
            "partner_name": inv.partner_id.name,
            "amount_total": inv.amount_total,
            "amount_residual": inv.amount_residual,
            "state": inv.state,
            "payment_state": inv.payment_state,
        } for inv in invoices]

    @api.model
    def post_invoice(self, invoice_id):
        inv = self.browse(int(invoice_id)).exists()
        if not inv:
            raise UserError(_("Invoice not found."))
        if inv.state == "draft":
            inv.action_post()
        return True

    @api.model
    def pos_register_payment(self, invoice_id, journal_id, amount, pos_session_id=None, pos_config_id=None):
        """Register a payment for an invoice from an open POS session.

        NOTE:
        - Invoice payment logic is kept as-is (account.payment.register wizard).
        - We DO NOT try to settle into POS cash/bank statements anymore.
        - We only LOG the invoice number + amount against the POS session so it
          can be printed in the Daily Sale PDF report.
        """
        inv = self.browse(int(invoice_id)).exists()
        if not inv:
            raise UserError(_("Invoice not found."))

        if inv.state == "draft":
            inv.action_post()

        if inv.payment_state == "paid":
            return True

        # --- Original payment logic (unchanged) ---
        wiz = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=[inv.id],
        ).create({
            "payment_date": fields.Date.context_today(self),
            "journal_id": int(journal_id),
            "amount": float(amount),
        })
        wiz.action_create_payments()

        # Try to fetch the created payment for linking
        payment = False
        if hasattr(wiz, "payment_ids") and wiz.payment_ids:
            payment = wiz.payment_ids[0]
        if not payment:
            payment = (
                self.env["account.payment"]
                .search(
                    [
                        ("journal_id", "=", int(journal_id)),
                        ("amount", "=", float(amount)),
                        ("partner_id", "=", inv.partner_id.id),
                        ("state", "in", ("posted", "in_process")),
                    ],
                    order="id desc",
                    limit=1,
                )
            )

        # --- POS session logging for PDF report ---
        if not pos_session_id and self.env.context.get("from_pos") and pos_config_id:
            config = self.env["pos.config"].browse(int(pos_config_id)).exists()
            if config and config.current_session_id:
                pos_session_id = config.current_session_id.id

        if pos_session_id:
            session = self.env["pos.session"].browse(int(pos_session_id)).exists()
            if session:
                journal = self.env["account.journal"].browse(int(journal_id)).exists()
                lines_model = self.env["pos.session.invoice.paid"].sudo()
                domain = [("session_id", "=", session.id), ("invoice_id", "=", inv.id)]
                if payment:
                    domain.append(("payment_id", "=", payment.id))
                else:
                    domain.extend([
                        ("journal_id", "=", journal.id if journal else False),
                        ("amount", "=", float(amount)),
                    ])

                # Create one log per payment per session (dedup safe)
                if not lines_model.search(domain, limit=1):
                    lines_model.create({
                        "session_id": session.id,
                        "invoice_id": inv.id,
                        "payment_id": payment.id if payment else False,
                        "journal_id": journal.id if journal else False,
                        "amount": float(amount),
                        "currency_id": (
                            inv.currency_id
                            or session.currency_id
                            or session.company_id.currency_id
                        ).id,
                    })

                if payment and not payment.pos_session_id:
                    payment.sudo().write({"pos_session_id": session.id})

        return True
