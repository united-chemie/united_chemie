import frappe

def validate(self, method):
    if self.stock_entry_type == "Manufacture" and self.work_order:
        abbr = frappe.db.get_value("Company", self.company, "abbr")
        for row in self.additional_costs:
            if row.expense_account:
                row.expense_account = f"{row.description}"
    
    set_yield(self, method)

def set_yield(doc, method):
    if doc.purpose == "Repack":
        source_rows = []
        target_rows = []

        for row in doc.items:
            if row.s_warehouse:
                source_rows.append(row)

            if row.t_warehouse:
                target_rows.append(row)

        if target_rows and source_rows:
            source_count = len(source_rows)
            for target_row in target_rows:
                item_group = target_row.item_group
                if item_group not in [
                    "Semi Finished- Liquid",
                    "Semi Finished- Powder"
                ]:
                    continue

                if not target_row.item_code or not target_row.qty:
                    continue

                default_bom = frappe.db.get_value("Item", target_row.item_code,"default_bom")
                if not default_bom:
                    continue

                based_on_item = frappe.db.get_value("BOM", default_bom,"based_on")

                if not based_on_item:
                    continue

                bom_item_qty = frappe.db.get_value(
                    "BOM Item",
                    {
                        "parent": default_bom,
                        "parenttype": "BOM",
                        "item_code": based_on_item
                    },
                    "qty"
                )

                if not bom_item_qty:
                    continue

                qty_per_source = target_row.qty / source_count
                yield_value = qty_per_source / bom_item_qty
                target_row.batch_yield = yield_value
                doc.batch_yield = yield_value