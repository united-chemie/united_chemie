import frappe
from frappe.utils import flt

def validate(self, method):
    if self.stock_entry_type == "Manufacture" and self.work_order:
        abbr = frappe.db.get_value("Company", self.company, "abbr")
        for row in self.additional_costs:
            if row.expense_account:
                row.expense_account = f"{row.description}"
    
    set_yield(self, method)

def set_yield(doc, method):
    def update_batch_yield(row):
        """
        Update Batch Yield if batch already exists.
        This is useful during Draft/Validate.
        """
        if not row.batch_no or not row.batch_yield:
            return

        if frappe.db.exists("Batch", row.batch_no):
            frappe.db.set_value("Batch",row.batch_no,"batch_yield",row.batch_yield)

    def set_transfer_yield():
        source_rows = [
            row for row in doc.items
            if row.s_warehouse and row.batch_no
        ]

        target_rows = [
            row for row in doc.items
            if row.t_warehouse
        ]

        if not source_rows or not target_rows:
            return

        target_qty = sum(
            flt(row.qty)
            for row in target_rows
            if row.item_code
        )

        if not target_qty:
            return

        total_yield = 0
        for row in source_rows:
            batch_yield = frappe.db.get_value("Batch",row.batch_no,"batch_yield")

            if batch_yield is None:
                continue

            row_yield = (
                flt(row.qty) / target_qty
            ) * flt(batch_yield)

            row.batch_yield = row_yield
            total_yield += row_yield

        for target_row in target_rows:
            target_row.batch_yield = total_yield

            update_batch_yield(target_row)

        doc.batch_yield = total_yield

    if doc.purpose == "Repack":

        source_rows = []
        target_rows = []

        for row in doc.items:

            if row.s_warehouse:
                source_rows.append(row)

            if row.t_warehouse:
                target_rows.append(row)

        if not target_rows or not source_rows:
            return

        source_count = len(source_rows)

        for target_row in target_rows:

            if not target_row.item_code or not target_row.qty:
                continue

            default_bom = frappe.db.get_value("Item",target_row.item_code,"default_bom")

            if not default_bom:
                set_transfer_yield()
                return

            based_on_item = frappe.db.get_value("BOM",default_bom,"based_on")
            if not based_on_item:
                set_transfer_yield()
                return

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
                set_transfer_yield()
                return

            qty_per_source = target_row.qty / source_count
            yield_value = (
                qty_per_source / bom_item_qty
            )

            target_row.batch_yield = yield_value

            doc.batch_yield = yield_value

            update_batch_yield(target_row)

    elif (
        doc.purpose == "Material Transfer"
        and doc.stock_entry_type == "Internal Transfer"
    ):
        set_transfer_yield()