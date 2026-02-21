/** @odoo-module */

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { CreatePaymentPopup } from "./payment_popup";

export class InvoicingScreen extends Component {
    static template = "pos_invoice_payment.InvoicingScreen";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.state = useState({ invoices: [] });

        onWillStart(async () => {
            await this.loadInvoices();
        });
    }

    async loadInvoices() {
        this.state.invoices = await this.orm.call("account.move", "get_invoices", []);
    }

    back() {
        this.pos.closeScreen();
    }

    async confirmInvoice(invoiceId) {
        await this.orm.call("account.move", "post_invoice", [invoiceId]);
        await this.loadInvoices();
    }

    async registerPayment(invoice) {
        const payload = await makeAwaitable(this.env.services.dialog, CreatePaymentPopup, {
            title: "Register Payment",
            invoice,
        });
        if (payload?.confirmed) {
            await this.orm.call("account.move", "pos_register_payment", [
                invoice.invoice_id,
                payload.journal_id,
                payload.amount,
                this.pos?.session?.id || null,
                this.pos?.config?.id || null,
            ], {
                context: { from_pos: true },
            });
            await this.loadInvoices();
        }
    }
}

registry.category("pos_screens").add("InvoicingScreen", InvoicingScreen);
