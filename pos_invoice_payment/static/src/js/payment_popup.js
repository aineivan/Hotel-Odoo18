/** @odoo-module */

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class CreatePaymentPopup extends Component {
    static template = "pos_invoice_payment.CreatePaymentPopup";
    static components = { Dialog };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            amount: this.props.invoice?.amount_residual || 0,
            journal_id: null,
            journals: [],
        });

        onWillStart(async () => {
            this.state.journals = await this.orm.call("account.journal", "get_journal", []);
            this.state.journal_id = this.state.journals?.[0]?.id || null;
        });
    }

    confirm() {
        this.props.getPayload({
            confirmed: true,
            amount: this.state.amount,
            journal_id: this.state.journal_id,
        });
        this.props.close();
    }

    cancel() {
        this.props.getPayload({ confirmed: false });
        this.props.close();
    }
}
