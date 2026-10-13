/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

patch(OrderSummary.prototype, {
  setup() {
    super.setup();
    this.notification = useService("notification");
    console.log("KOT: OrderSummary patched");
  },

  async onSelectWaiter() {
    try {
      const employeeModel = this.pos.models["hr.employee"];
      if (!employeeModel) {
        throw new Error("Employees not loaded in POS!");
      }

      const waiters = employeeModel.getAll().filter((e) => e.is_waiter);

      if (waiters.length === 0) {
        this.notification.add(
          "No waiters found. Ensure employees are marked as 'Is Waiter' in HR settings.",
          { type: "warning" }
        );
        return;
      }

      const currentOrder = this.pos.getOrder();
      const selectionList = waiters.map((waiter) => ({
        id: waiter.id,
        label: waiter.name,
        item: waiter,
        isSelected: currentOrder?.waiter_id?.id === waiter.id,
      }));

      const selectedWaiter = await makeAwaitable(this.dialog, SelectionPopup, {
        title: _t("Select Waiter"),
        list: selectionList,
      });

      if (selectedWaiter) {
        await this._setWaiterForOrder(selectedWaiter);
      }
    } catch (error) {
      console.error("KOT waiter selection error:", error);
      this.notification.add("Selection Error: " + error.message, { type: "danger" });
    }
  },

  async _setWaiterForOrder(waiter) {
    const currentOrder = this.pos.getOrder();
    if (!currentOrder) {
      this.notification.add("No active order found", { type: "warning" });
      return;
    }

    try {
      currentOrder.waiter_id = waiter;
      currentOrder.waiter_name = waiter.name;

      this.notification.add(`Waiter ${waiter.name} assigned to order`, {
        type: "success",
      });

      this.pos.addPendingOrder([currentOrder.id]);
      this.pos.syncAllOrdersDebounced();
    } catch (error) {
      console.error("KOT set waiter error:", error);
      this.notification.add("Failed to assign waiter: " + error.message, {
        type: "danger",
      });
    }
  },

  get currentWaiter() {
    const order = this.pos.getOrder();
    if (order) {
      if (order.waiter_id) return order.waiter_id;
      const cashier = this.pos.getCashier();
      const employeeModel = this.pos.models["hr.employee"];
      if (cashier && employeeModel) {
        const emp = employeeModel.getAll().find(
          (e) => e.name === cashier.name || e.id === cashier.employee_id?.id
        );
        if (emp) return emp;
      }
    }
    return null;
  },

  _getWaiterName(order) {
    if (order.waiter_name) return order.waiter_name;

    if (order.waiter_id) {
      if (typeof order.waiter_id === "object" && order.waiter_id.name) {
        return order.waiter_id.name;
      }

      if (typeof order.waiter_id === "number") {
        const employeesModel = this.pos.models["hr.employee"];
        if (employeesModel) {
          const employee = employeesModel.get(order.waiter_id);
          if (employee && employee.name) {
            return employee.name;
          }
        }
      }
    }

    return "Not assigned";
  },

  async onPrintKOT() {
    const order = this.pos.getOrder();
    const orderLines = order ? order.getOrderlines() : [];

    if (!order || orderLines.length === 0) {
      this.notification.add("Please add products to the order first!", {
        type: "warning",
      });
      return;
    }

    if (!order.waiter_id) {
      const cashier = this.pos.getCashier();
      const employeeModel = this.pos.models["hr.employee"];
      if (cashier && employeeModel) {
        const matchingEmployee = employeeModel.getAll().find(
          (e) => e.name === cashier.name || e.id === cashier.employee_id?.id
        );
        if (matchingEmployee) {
          order.waiter_id = matchingEmployee;
          order.waiter_name = matchingEmployee.name;
        }
      }
    }

    try {
      const baristaItems = [];
      const kitchenItems = [];
      const otherItems = [];

      orderLines.forEach((line) => {
        const product = line.getProduct();
        if (!product) return;

        let isBarista = false;
        let isKitchen = false;

        if (product.pos_categ_id) {
          const mainCategId = Array.isArray(product.pos_categ_id)
            ? product.pos_categ_id[0]
            : product.pos_categ_id.id || product.pos_categ_id;

          const category = this.pos.models["pos.category"].get(mainCategId);
          if (category) {
            if (category.is_barista) isBarista = true;
            if (category.is_kitchen) isKitchen = true;
          }
        }

        const extraCategIds = product.pos_categ_ids || [];
        extraCategIds.forEach(id => {
            const cat = this.pos.models["pos.category"].get(id);
            if (cat?.is_barista) isBarista = true;
            if (cat?.is_kitchen) isKitchen = true;
        });

        if (isBarista) {
          baristaItems.push(line);
        } else if (isKitchen) {
          kitchenItems.push(line);
        } else {
          otherItems.push(line);
        }
      });

      const kotHtml = this._generateKOTHTML(
        order,
        baristaItems,
        kitchenItems,
        otherItems,
      );
      this._openPrintWindow(kotHtml, "Kitchen Order Ticket");

      order.kot_printed = true;
      this.pos.addPendingOrder([order.id]);
      this.pos.syncAllOrdersDebounced();

      this.notification.add("KOT printed successfully", { type: "success" });
    } catch (error) {
      console.error("KOT printing error:", error);
      this.notification.add("Failed to print KOT: " + error.message, {
        type: "danger",
      });
    }
  },

  _generateKOTHTML(order, baristaItems, kitchenItems, otherItems) {
    const getCurrentTime = () => {
      return new Date().toLocaleString("en-US", {
        month: "2-digit",
        day: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      });
    };

    const orderTime = order.creation_date
      ? new Date(order.creation_date).toLocaleString("en-US", {
          month: "2-digit",
          day: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          hour12: true,
        })
      : getCurrentTime();

    let baristaHtml = "";
    if (baristaItems.length > 0) {
      baristaHtml = `
        <div class="section-header">BARISTA</div>
        <div class="section-divider"></div>
      `;

      baristaItems.forEach((line) => {
        const quantity = line.qty || 1;
        const productName = line.getProduct
          ? line.getProduct().display_name
          : line.product_id?.display_name || "Product";

        const noteText = this._getLineNote(line);
        const attributesHtml = this._getLineAttributes(line);

        baristaHtml += `
          <div class="line-item">
            <div class="line-header">
              <span class="qty">${quantity}x</span>
              <span class="product">${productName}</span>
            </div>
            ${noteText ? `<div class="line-note">Note: ${noteText}</div>` : ""}
            ${attributesHtml}
          </div>
        `;
      });
    }

    let kitchenHtml = "";
    if (kitchenItems.length > 0) {
      const marginTop = baristaItems.length > 0 ? "15px" : "0";

      kitchenHtml = `
        <div class="section-header" style="margin-top: ${marginTop};">KITCHEN</div>
        <div class="section-divider"></div>
      `;

      kitchenItems.forEach((line) => {
        const quantity = line.qty || 1;
        const productName = line.getProduct
          ? line.getProduct().display_name
          : line.product_id?.display_name || "Product";

        const noteText = this._getLineNote(line);
        const attributesHtml = this._getLineAttributes(line);

        kitchenHtml += `
          <div class="line-item">
            <div class="line-header">
              <span class="qty">${quantity}x</span>
              <span class="product">${productName}</span>
            </div>
            ${noteText ? `<div class="line-note">Note: ${noteText}</div>` : ""}
            ${attributesHtml}
          </div>
        `;
      });
    }

    let otherHtml = "";
    if (otherItems.length > 0) {
      const marginTop =
        baristaItems.length > 0 || kitchenItems.length > 0 ? "15px" : "0";

      otherHtml = `
        <div class="section-header" style="margin-top: ${marginTop};">OTHER ITEMS</div>
        <div class="section-divider"></div>
      `;

      otherItems.forEach((line) => {
        const quantity = line.qty || 1;
        const productName = line.getProduct
          ? line.getProduct().display_name
          : line.product_id?.display_name || "Product";

        const noteText = this._getLineNote(line);
        const attributesHtml = this._getLineAttributes(line);

        otherHtml += `
          <div class="line-item">
            <div class="line-header">
              <span class="qty">${quantity}x</span>
              <span class="product">${productName}</span>
            </div>
            ${noteText ? `<div class="line-note">Note: ${noteText}</div>` : ""}
            ${attributesHtml}
          </div>
        `;
      });
    }

    const tableName = order.table?.name || order.table_id?.name || "No Table";
    const tableFloor =
      order.table?.floor?.name || order.table_id?.floor_id?.name || "";
    const orderReference = order.pos_reference || order.name || "N/A";

    const waiterName = this._getWaiterName(order);

    const cashierName =
      (this.pos.getCashier && this.pos.getCashier().name) ||
      this.pos.cashier?.name ||
      this.pos.user?.name ||
      "Unknown";

    let orderMode = "Dine In";
    if (order.preset?.name) {
      orderMode = order.preset.name;
    } else if (order.preset_id?.name) {
      orderMode = order.preset_id.name;
    } else if (order.takeaway) {
      orderMode = "Takeaway";
    } else if (order.delivery_mode) {
      orderMode = "Delivery";
    }

    const customerName = order.partner_id?.name || order.customer?.name || null;
    const customerHtml = customerName
      ? `<div class="customer-info">Customer: ${customerName}</div>`
      : "";

    return `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Kitchen Order Ticket</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: 'Courier New', monospace;
            padding: 10px;
            font-size: 12px;
            line-height: 1.3;
            font-weight: bold !important;
          }
          .kot-receipt {
            max-width: 280px;
            margin: 0 auto;
          }
          .header {
            text-align: center;
            border-bottom: 2px solid #000;
            padding-bottom: 8px;
            margin-bottom: 10px;
            font-weight: bold;
          }
          .header-title {
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 8px;
          }
          .header-info {
            font-size: 12px;
            font-weight: bold;
            margin: 3px 0;
          }
          .customer-info {
            font-weight: bold;
            color: #000;
            margin-top: 2px;
          }
          .info-table {
            width: 100%;
            margin: 10px 0;
            font-weight: bold;
          }
          .info-table td {
            padding: 2px 0;
            font-size: 12px;
            font-weight: bold;
          }
          .info-table td:first-child { width: 40%; }
          .section-header {
            font-weight: bold;
            font-size: 14px;
            text-align: center;
            padding: 8px 0;
            background: #f0f0f0;
            border-radius: 3px;
            margin-bottom: 8px;
          }
          .section-divider {
            border-bottom: 2px dashed #000;
            margin: 5px 0 10px 0;
          }
          .line-item {
            margin: 8px 0;
            padding: 5px 0;
            border-bottom: 1px dashed #ccc;
            font-weight: bold;
          }
          .line-header {
            font-weight: bold;
            display: flex;
            gap: 8px;
          }
          .qty {
            font-weight: bold;
            min-width: 30px;
          }
          .product {
            flex: 1;
            font-weight: bold;
          }
          .line-note {
            padding-left: 10px;
            font-weight: bold;
            color: #000;
            margin-top: 3px;
            font-size: 11px;
          }
          .attributes {
            padding-left: 10px;
            color: #444;
            margin-top: 3px;
            font-size: 11px;
            font-weight: bold;
          }
          .footer {
            text-align: center;
            border-top: 2px solid #000;
            padding-top: 8px;
            margin-top: 15px;
            font-size: 11px;
            font-weight: bold;
          }
          @media print {
            body { padding: 5px; font-weight: bold !important; }
            .no-print { display: none; }
            * { font-weight: bold !important; }
          }
        </style>
      </head>
      <body>
        <div class="kot-receipt">
          <div class="header">
            <div class="header-title">KITCHEN ORDER TICKET</div>
            <div class="header-info">Waiter: ${waiterName}</div>
            <div class="header-info">Created By: ${cashierName}</div>
            <div class="header-info">Mode: ${orderMode}</div>
            ${customerHtml}
          </div>

          <table class="info-table">
            <tr><td>Order #:</td><td>${orderReference}</td></tr>
            <tr><td>Order Time:</td><td>${orderTime}</td></tr>
            ${tableFloor ? `<tr><td>Floor:</td><td>${tableFloor}</td></tr>` : ""}
            ${tableName !== "No Table" ? `<tr><td>Table:</td><td>${tableName}</td></tr>` : ""}
          </table>

          ${baristaHtml}
          ${kitchenHtml}
          ${otherHtml}

          <div class="footer">
            <div style="font-weight: bold;">Printed: ${getCurrentTime()}</div>
            <div style="margin-top: 5px; font-size: 10px; font-weight: bold;">
              Sections:
              ${baristaItems.length > 0 ? "Barista " : ""}${kitchenItems.length > 0 ? "Kitchen " : ""}${otherItems.length > 0 ? "Other" : ""}
            </div>
          </div>
        </div>

        <div class="no-print" style="text-align: center; margin-top: 20px;">
          <button onclick="window.print()" style="padding: 10px 20px; font-size: 12px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; margin: 5px;">
            Print / Save as PDF
          </button>
          <button onclick="window.close()" style="padding: 10px 20px; font-size: 12px; cursor: pointer; background: #6c757d; color: white; border: none; border-radius: 4px; margin: 5px;">
            Close
          </button>
        </div>

        <script>
          window.onload = function () {
            setTimeout(function () { window.print(); }, 500);
          };
        </script>
      </body>
      </html>
    `;
  },

  _getLineNote(line) {
    let noteText = "";
    if (line.note) {
      try {
        const parsed = JSON.parse(line.note);
        if (Array.isArray(parsed)) {
          noteText = parsed.map((n) => n.text).join(" ");
        } else if (typeof parsed === "object" && parsed.text) {
          noteText = parsed.text;
        } else {
          noteText = line.note;
        }
      } catch {
        noteText = line.note;
      }
    } else if (line.customer_note) {
      noteText = line.customer_note;
    }
    return noteText.trim();
  },

  _getLineAttributes(line) {
    if (!line.attribute_value_ids || line.attribute_value_ids.length === 0) {
      return "";
    }

    let attributesHtml = '<div class="attributes">';
    line.attribute_value_ids.forEach((attr) => {
      attributesHtml += `<div>• ${attr.name}</div>`;
    });
    attributesHtml += "</div>";

    return attributesHtml;
  },

  _openPrintWindow(htmlContent, title) {
    const printWindow = window.open(
      "",
      "_blank",
      "width=800,height=600,scrollbars=yes",
    );

    if (!printWindow) {
      this.notification.add("Please allow popups to print KOT", {
        type: "warning",
      });
      this._printUsingIframe(htmlContent);
      return;
    }

    printWindow.document.write(htmlContent);
    printWindow.document.close();
  },

  _printUsingIframe(html) {
    const iframe = document.createElement("iframe");
    iframe.style.position = "fixed";
    iframe.style.right = "0";
    iframe.style.bottom = "0";
    iframe.style.width = "0";
    iframe.style.height = "0";
    iframe.style.border = "none";
    document.body.appendChild(iframe);

    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(html);
    doc.close();

    iframe.onload = () => {
      setTimeout(() => {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
        setTimeout(() => {
          document.body.removeChild(iframe);
        }, 1000);
      }, 500);
    };
  },
});
