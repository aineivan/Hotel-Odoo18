/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

// Returns "YYYY-MM-DD" for a given Date object (local time)
function toDateStr(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

class HotelSummaryDashboard extends Component {
  static template = "hotel_summary_dashboard.HotelSummaryDashboard";

  setup() {
    this.action = useService("action");
    this.notification = useService("notification");
    this.orm = useService("orm");

    const today = toDateStr(new Date());

    this.state = useState({
      loading: true,
      error: null,
      view: "sales",       // sales | bookings | inventory | purchases | expenses
      searchQuery: "",
      currentPage: 1,
      itemsPerPage: 10,

      // Date filter – both default to today
      dateFrom: today,
      dateTo:   today,
      // Whether this user is allowed to pick a different date range at
      // all -- plain POS staff always see today only. The server is the
      // source of truth for this (see reload()); true here is just the
      // safe default before the first response arrives.
      canFilter: true,

      data: {
        cards: {
          inventory_value: 0,
          purchase_total:  0,
          total_sales:     0,
          total_cost:      0,
          gross_profit:    0,
          total_expenses:  0,
          active_bookings: 0,
          total_paid_amount: 0,
          sales_by_pos:    [],
          payment_breakdown_by_pos: [],
          payment_method_totals:    [],
          payment_grand_total:      0,
          room_occupancy:   { occupied: 0, unoccupied: 0, total_rooms: 0 },
        },
        lists: { inventory: [], purchases: [], sales: [], expenses: [], bookings: [] },
      },
    });

    onWillStart(async () => {
      await this.reload();
    });
  }

  // ── Data loading ──────────────────────────────────────────────────────────

  async reload() {
    this.state.loading = true;
    this.state.error   = null;
    try {
      const data = await rpc("/hotel_summary_dashboard/data", {
        limit:     200,
        date_from: this.state.dateFrom,
        date_to:   this.state.dateTo,
      });
      this.state.data = data;
      this.state.canFilter = data.can_filter !== false;
      if (!this.state.canFilter) {
        // The server ignored any range we sent and used today -- mirror
        // that back into the inputs so they can't drift from reality.
        this.state.dateFrom = data.date_from;
        this.state.dateTo   = data.date_to;
      }
      this.state.currentPage = 1;
    } catch (e) {
      this.state.error = e?.message || "Failed to load hotel summary dashboard.";
    } finally {
      this.state.loading = false;
    }
  }

  // ── Date filter handlers ──────────────────────────────────────────────────

  onDateFromChange(ev) {
    this.state.dateFrom = ev.target.value;
    if (this.state.dateTo < this.state.dateFrom) {
      this.state.dateTo = this.state.dateFrom;
    }
  }

  onDateToChange(ev) {
    this.state.dateTo = ev.target.value;
    if (this.state.dateFrom > this.state.dateTo) {
      this.state.dateFrom = this.state.dateTo;
    }
  }

  resetToToday() {
    const today = toDateStr(new Date());
    this.state.dateFrom = today;
    this.state.dateTo   = today;
    this.reload();
  }

  // ── View / search / pagination ────────────────────────────────────────────

  setView(view) {
    this.state.view = view;
    this.state.currentPage = 1;
    this.clearSearch();
  }

  onSearchInput(ev) {
    this.state.searchQuery = ev.target.value;
    this.state.currentPage = 1;
  }

  clearSearch() {
    this.state.searchQuery = "";
    this.state.currentPage = 1;
  }

  get currentList() {
    const lists = this.state.data?.lists || {};
    let items = lists[this.state.view] || [];

    const q = (this.state.searchQuery || "").trim().toLowerCase();
    if (!q) return items;

    return items.filter((item) => {
      const hay = [];
      if (this.state.view === "inventory") {
        hay.push(item.product, String(item.qty_available), String(item.unit_cost), String(item.total_value));
      } else if (this.state.view === "purchases") {
        hay.push(item.product, item.vendor, String(item.qty), String(item.unit_price), String(item.subtotal));
      } else if (this.state.view === "sales") {
        hay.push(item.product, item.category, String(item.qty_sold), String(item.profit));
      } else if (this.state.view === "expenses") {
        hay.push(item.employee, item.category, item.description, String(item.amount), String(item.state || ""));
      } else if (this.state.view === "bookings") {
        hay.push(item.room, item.customer, String(item.no_of_days), String(item.rate),
                 String(item.total_amount), String(item.state || ""));
      }
      return hay.join(" ").toLowerCase().includes(q);
    });
  }

  get totalPages() {
    return Math.ceil(this.currentList.length / this.state.itemsPerPage) || 0;
  }

  get paginationInfo() {
    const total = this.currentList.length;
    const start = total === 0 ? 0 : (this.state.currentPage - 1) * this.state.itemsPerPage + 1;
    const end   = Math.min(this.state.currentPage * this.state.itemsPerPage, total);
    return { start, end, total };
  }

  get paginatedList() {
    const start = (this.state.currentPage - 1) * this.state.itemsPerPage;
    return this.currentList.slice(start, start + this.state.itemsPerPage);
  }

  nextPage() {
    if (this.state.currentPage < this.totalPages) this.state.currentPage++;
  }

  prevPage() {
    if (this.state.currentPage > 1) this.state.currentPage--;
  }

  // ── PDF report download ─────────────────────────────────────────────────

  async downloadReport(reportType) {
    try {
      const ids = await this.orm.create("hotel.summary.dashboard.report", [{
        report_type: reportType,
        date_from:   this.state.dateFrom,
        date_to:     this.state.dateTo,
      }]);
      const reportAction = await this.orm.call(
        "hotel.summary.dashboard.report",
        "action_download_pdf",
        [ids[0]]
      );
      await this.action.doAction(reportAction);
    } catch (e) {
      this.notification.add(
        e?.data?.message || e?.message || "Failed to generate the report.",
        { type: "danger" }
      );
    }
  }

  // ── Drill-downs ───────────────────────────────────────────────────────────

  openProduct(product_id) {
    if (!product_id) return;
    return this.action.doAction({
      type:      "ir.actions.act_window",
      res_model: "product.product",
      res_id:    product_id,
      views:     [[false, "form"]],
      target:    "current",
    });
  }

  openPurchaseOrder(po_id) {
    if (!po_id) return;
    return this.action.doAction({
      type:      "ir.actions.act_window",
      res_model: "purchase.order",
      res_id:    po_id,
      views:     [[false, "form"]],
      target:    "current",
    });
  }

  openExpense(expense_id) {
    if (!expense_id) return;
    return this.action.doAction({
      type:      "ir.actions.act_window",
      res_model: "hr.expense",
      res_id:    expense_id,
      views:     [[false, "form"]],
      target:    "current",
    });
  }

  openBooking(booking_id) {
    if (!booking_id) return;
    return this.action.doAction({
      type:      "ir.actions.act_window",
      res_model: "room.booking",
      res_id:    booking_id,
      views:     [[false, "form"]],
      target:    "current",
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  fmtMoney(value) {
    const v = Number(value || 0);
    return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
}

registry.category("actions").add("hotel_summary_dashboard.HotelSummaryDashboard", HotelSummaryDashboard);

export default HotelSummaryDashboard;