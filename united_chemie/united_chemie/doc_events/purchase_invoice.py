import frappe
from frappe import _
from frappe.utils import flt


def validate_conversion_rate_purchase_invoice(doc, method=None):
    if doc.is_new():
        validate_purchase_receipt_rate(doc)
        return

    old_doc = doc.get_doc_before_save()
    if old_doc and flt(doc.conversion_rate) != flt(old_doc.conversion_rate):
        frappe.throw(("Conversion Rate cannot be changed."))


def validate_purchase_receipt_rate(doc):
    for item in doc.items:
        if not item.purchase_receipt:
            continue

        purchase_receipt_rate = frappe.db.get_value(
            "Purchase Receipt", item.purchase_receipt, "conversion_rate"
        )
        if flt(doc.conversion_rate) != flt(purchase_receipt_rate):
            frappe.throw(("Conversion Rate cannot be changed from the Purchase Receipt rate."))