import frappe
from frappe.utils import flt

def before_save(self,method):
    calculate_inr_freight(self)

def calculate_inr_freight(self):
    conversion_rate = flt(self.conversion_rate)

    for row in self.items:
        row.base_freight = flt(row.freight) * conversion_rate
        row.base_insurance = flt(row.insurance) * conversion_rate
        row.base_fob_value = flt(row.fob_value) / conversion_rate if conversion_rate else 0

    self.base_freight = flt(self.freight) * conversion_rate
    self.base_insurance = flt(self.insurance) * conversion_rate
    self.base_fob_value = flt(self.total_fob_value) / conversion_rate if conversion_rate else 0

def on_submit(self, method):
    for row in self.items:
        if row.so_detail:
            frappe.db.set_value("Sales Order Item", row.so_detail, "sales_invoice", self.name)
            frappe.db.commit()

def on_update_after_submit(self, method):
    if self.brc_no:
        frappe.db.set_value("Export Against AAL", {"sales_invoice": self.name}, "brc_no", self.brc_no)
