import frappe

def validate(self, method):
    set_actual_stock(self, method)

def set_actual_stock(doc, method):
    for row in doc.po_items:
        if not row.item_code or not row.warehouse:
            row.actual_stock = 0
            continue

        actual_qty = frappe.db.get_value(
            "Bin",
            {
                "item_code": row.item_code,
                "warehouse": row.warehouse
            },
            "actual_qty"
        )

        row.actual_qty = actual_qty or 0