/** © 2025 ehuerta _at_ ixer.mx
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).
 */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { formatFloat, roundPrecision } from "@web/core/utils/numbers";


patch(PosOrderline.prototype, {
    setup() {
        super.setup(...arguments);
        this.product_uom_id = this.product_uom_id || this.product_id.uom_id;
        const allLineToRefundUuids = this.models["pos.order"].reduce((acc, order) => {
            Object.assign(acc, order.uiState.lineToRefund);
            return acc;
        }, {});
        if (this.refunded_orderline_id?.uuid in allLineToRefundUuids) {
            this.product_uom_id = this.refunded_orderline_id.product_uom_id;
        }
    },
     set_uom(uom_id) {
        this.product_uom_id = uom_id;
    },
    get quantityStr() {
        let qtyStr = "";
        const unit = this.product_uom_id;

        if (unit) {
            if (unit.rounding) {
                const decimals = this.models["decimal.precision"].find(
                    (dp) => dp.name === "Product Unit of Measure"
                ).digits;
                qtyStr = formatFloat(this.qty, {
                    digits: [69, decimals],
                });
            } else {
                qtyStr = this.qty.toFixed(0);
            }
        } else {
            qtyStr = "" + this.qty;
        }

        return qtyStr;
    },
    set_quantity(quantity, keep_price) {
        this.order_id.assert_editable();
        const quant =
            typeof quantity === "number" ? quantity : parseFloat("" + (quantity ? quantity : 0));

        const allLineToRefundUuids = this.models["pos.order"].reduce((acc, order) => {
            Object.assign(acc, order.uiState.lineToRefund);
            return acc;
        }, {});

        if (this.refunded_orderline_id?.uuid in allLineToRefundUuids) {
            const refundDetails = allLineToRefundUuids[this.refunded_orderline_id.uuid];
            const maxQtyToRefund = refundDetails.line.qty - refundDetails.line.refunded_qty;
            if (quant > 0) {
                return {
                    title: _t("Positive quantity not allowed"),
                    body: _t(
                        "Only a negative quantity is allowed for this refund line. Click on +/- to modify the quantity to be refunded."
                    ),
                };
            } else if (quant == 0) {
                refundDetails.qty = 0;
            } else if (-quant <= maxQtyToRefund) {
                refundDetails.qty = -quant;
            } else {
                return {
                    title: _t("Greater than allowed"),
                    body: _t(
                        "The requested quantity to be refunded is higher than the refundable quantity."
                    ),
                };
            }
        }
        const unit = this.product_uom_id;
        if (unit) {
            if (unit.rounding) {
                const decimals = this.models["decimal.precision"].find(
                    (dp) => dp.name === "Product Unit of Measure"
                ).digits;
                const rounding = Math.max(unit.rounding, Math.pow(10, -decimals));
                this.qty = roundPrecision(quant, rounding);
            } else {
                this.qty = roundPrecision(quant, 1);
            }
        } else {
            this.qty = quant;
        }

        // just like in sale.order changing the qty will recompute the unit price
        if (!keep_price && this.price_type === "original") {
            this.set_unit_price(
                this.product_id.get_price(
                    this.order_id.pricelist_id,
                    this.get_quantity(),
                    this.get_price_extra()
                )
            );
        }

        this.setDirty();
        return true;
    },
    getDisplayData() {
        const vals = super.getDisplayData(...arguments);
        vals.unit = this.product_uom_id ? this.product_uom_id.name : "";
        return vals;
    },
    get_unit() {
        return this.product_uom_id;
    },
    is_pos_groupable() {
        const unit_groupable = this.product_uom_id
            ? this.product_uom_id.is_pos_groupable
            : false;
        return unit_groupable && !this.isPartOfCombo();
    }


});
