import frappe

# def validate(self,method):
#     if self.stock_entry_type == "Manufacture" and self.work_order:
#         abbr = frappe.db.get_value("Company", self.company, "abbr")
#         for row in self.additional_costs:
#             if row.expense_account:
#                 expense_account = f"{items.description} - {abbr}"
#                 row.expense_account = expense_account

def validate(self, method):
    if self.stock_entry_type == "Manufacture" and self.work_order:
        abbr = frappe.db.get_value("Company", self.company, "abbr")
        for row in self.additional_costs:
            if row.expense_account:
                row.expense_account = f"{row.description}"
