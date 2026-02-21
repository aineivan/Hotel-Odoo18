/** @odoo-module */

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";

const extraProps = ["invoice_paid_lines", "invoice_paid_total"];
ClosePosPopup.props = [...new Set([...(ClosePosPopup.props || []), ...extraProps])];
