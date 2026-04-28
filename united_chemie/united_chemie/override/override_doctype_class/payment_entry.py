from erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import get_party_tax_withholding_details
import frappe
import erpnext
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry as _PaymentEntry
from frappe.utils.data import flt

class PaymentEntry(_PaymentEntry):
	def set_tax_withholding(self):
		if not self.party_type == "Supplier":
			return

		if not self.apply_tax_withholding_amount:
			return

		net_total = self.calculate_tax_withholding_net_total()

		# Adding args as purchase invoice to get TDS amount
		args = frappe._dict(
			{
				"company": self.company,
				"doctype": "Payment Entry",
				"supplier": self.party,
				"posting_date": self.posting_date,
				"net_total": net_total,
			}
		)

		tax_withholding_details = get_party_tax_withholding_details(args, self.tax_withholding_category)

		if not tax_withholding_details:
			return

		tax_withholding_details.update(
			{"cost_center": self.cost_center or erpnext.get_default_cost_center(self.company)}
		)

		accounts = []
		for d in self.taxes:
			if d.account_head == tax_withholding_details.get("account_head"):
				# Preserve user updated included in paid amount
				if d.included_in_paid_amount:
					tax_withholding_details.update({"included_in_paid_amount": d.included_in_paid_amount})
				tax_withholding_details.update({"add_deduct_tax": d.add_deduct_tax})

				d.update(tax_withholding_details)
			accounts.append(d.account_head)

		if not accounts or tax_withholding_details.get("account_head") not in accounts:
			self.append("taxes", tax_withholding_details)

		to_remove = [
			d
			for d in self.taxes
			if not d.tax_amount and d.account_head == tax_withholding_details.get("account_head")
		]

		for d in to_remove:
			self.remove(d)
