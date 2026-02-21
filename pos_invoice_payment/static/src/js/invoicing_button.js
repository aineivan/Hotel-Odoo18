/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

/**
 * Add "Invoices" button just above the numpad area in the Product Screen.
 */
patch(ProductScreen.prototype, {
    onClickInvoicePayments() {
        this.pos.showScreen("InvoicingScreen");
    },
});
