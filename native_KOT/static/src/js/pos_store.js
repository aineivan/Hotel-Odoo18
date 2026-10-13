/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";

patch(PosStore.prototype, {
    async selectWaiter() {
        const currentOrder = this.get_order();
        if (!currentOrder) {
            this.notification.add("No active order found!", { type: "danger" });
            return;
        }

        const employeeModel = this.models["hr.employee"];
        if (!employeeModel) {
            this.notification.add("Employee data not loaded", { type: "danger" });
            return;
        }

        const waiters = employeeModel.getAll().filter((employee) => employee.is_waiter === true);

        if (!waiters.length) {
            this.notification.add("No waiters available! Ensure 'Is Waiter' is checked in Employee settings.", { type: "warning" });
            return;
        }

        const selectionList = waiters.map((waiter) => ({
            id: waiter.id,
            label: waiter.name,
            isSelected: currentOrder.waiter_id && waiter.id === currentOrder.waiter_id.id,
            item: waiter,
        }));

        selectionList.unshift({
            id: null,
            label: "No Waiter",
            isSelected: !currentOrder.waiter_id,
            item: null,
        });

        const selectedWaiter = await makeAwaitable(this.dialog, SelectionPopup, {
            title: "Select Waiter",
            list: selectionList,
        });

        if (selectedWaiter !== undefined) {
            currentOrder.waiter_id = selectedWaiter;
            currentOrder.waiter_name = selectedWaiter?.name || null;

            const message = selectedWaiter
                ? `Waiter set to: ${selectedWaiter.name}`
                : "Waiter removed";

            this.notification.add(message, { type: "success" });

            this.addPendingOrder([currentOrder.id]);
            this.syncAllOrdersDebounced();
        }
    },

    get currentWaiter() {
        const order = this.get_order();
        return order ? order.waiter_id : null;
    },
});

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.kot_printed = this.kot_printed || false;
    },
});
