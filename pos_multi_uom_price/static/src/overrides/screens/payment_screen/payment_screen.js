/** © 2025 ehuerta _at_ ixer.mx
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).
 */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        this.numberBuffer.capture();
        if (!this.check_cash_rounding_has_been_well_applied()) {
            return;
        }
        const linesToRemove = this.currentOrder.lines.filter((line) => {
            const rounding = line.product_uom_id.rounding;
            const decimals = Math.max(0, Math.ceil(-Math.log10(rounding)));
            return floatIsZero(line.qty, decimals);
        });
        for (const line of linesToRemove) {
            this.currentOrder.removeOrderline(line);
        }
        if (await this._isOrderValid(isForceValidate)) {
            // remove pending payments before finalizing the validation
            const toRemove = [];
            for (const line of this.paymentLines) {
                if (!line.is_done() || line.amount === 0) {
                    toRemove.push(line);
                }
            }

            for (const line of toRemove) {
                this.currentOrder.remove_paymentline(line);
            }
            await this._finalizeValidation();
        }
    }
});
