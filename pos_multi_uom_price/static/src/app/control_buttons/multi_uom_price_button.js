/** © 2025 ehuerta _at_ ixer.mx
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).
 */

import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { makeAwaitable, ask } from "@point_of_sale/app/store/make_awaitable_dialog";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";

patch(ControlButtons.prototype, {
    async onClickUOMSelector() {
	const selectedLine = this.currentOrder.get_selected_orderline();
    if (!selectedLine) {
        this.dialog.add(AlertDialog, {
            title: _t("No product"),
            body: _t("Select a product line first."),
        });
        return;
    }
    let uom_price = null;
    if (this.pos.models["product.multi.uom.price"].filter(rec => rec.product_id.id === selectedLine.product_id.id ).length ) {
        uom_price = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("UOM"),
            list: this.pos.models["product.multi.uom.price"].filter((rec) => rec.product_id.id === selectedLine.product_id.id).map((rec) => (
                {id: rec.uom_id.id,
                 label: rec.uom_id.name,
                 item: rec,
                 isSelected: true,
                 }))
        });
    }
    if (uom_price){
        selectedLine.set_unit_price(uom_price.price);
        selectedLine.price_type = "manual";
        selectedLine.set_uom(uom_price.uom_id)
    }

    },
});
