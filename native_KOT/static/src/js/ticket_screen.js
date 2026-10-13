/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

patch(TicketScreen.prototype, {
    shouldHideDeleteButton(order) {
        if (
            order.kot_printed &&
            this.pos.get_cashier()?.role !== 'manager'
        ) {
            return true;
        }
        return super.shouldHideDeleteButton(...arguments);
    },
});
