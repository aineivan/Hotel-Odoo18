/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
  async setup() {
    await super.setup(...arguments);
    if (this.models && this.models["pos.category"]) {
      const categories = this.models["pos.category"].getAll();
      categories.forEach((category) => {
        console.log(`Category: "${category.name}"`, {
          is_barista: category.is_barista,
          is_kitchen: category.is_kitchen,
          id: category.id,
        });
      });
    }
  },
});
