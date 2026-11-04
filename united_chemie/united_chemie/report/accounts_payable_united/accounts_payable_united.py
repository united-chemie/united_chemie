# Copyright (c) 2026, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport


def execute(filters=None):
	args = {
		"account_type": "Payable",
		"naming_by": ["Buying Settings", "supp_master_name"],
	}
	return AccountsPayableUnited(filters).run(args)


class AccountsPayableUnited(ReceivablePayableReport):
	def update_voucher_balance(self, ple):
		row = self.get_voucher_balance(ple)
		if not row:
			return

		# In Accounts Payable-United:
		# If "In Party Currency" is ticked, show amounts in party/account currency.
		# Otherwise, always show amounts in company base currency (INR)
		# even if the selected party_account has a foreign currency (USD, EUR, etc.)
		if self.filters.get("in_party_currency"):
			amount = ple.amount_in_account_currency
		else:
			amount = ple.amount
		amount_in_account_currency = ple.amount_in_account_currency

		# update voucher
		if ple.amount > 0:
			if (
				ple.voucher_type in ["Journal Entry", "Payment Entry"]
				and ple.voucher_no != ple.against_voucher_no
			):
				row.paid -= amount
				row.paid_in_account_currency -= amount_in_account_currency
			else:
				row.invoiced += amount
				row.invoiced_in_account_currency += amount_in_account_currency
		else:
			if self.is_invoice(ple):
				if row.voucher_no == ple.voucher_no == ple.against_voucher_no:
					row.paid -= amount
					row.paid_in_account_currency -= amount_in_account_currency
				else:
					row.credit_note -= amount
					row.credit_note_in_account_currency -= amount_in_account_currency
			else:
				row.paid -= amount
				row.paid_in_account_currency -= amount_in_account_currency

	def get_party_details(self, party):
		if party not in self.party_details:
			party_type = (
				self.filters.get("party_type")
				or (self.party_type[0] if isinstance(self.party_type, list) else self.party_type)
				or "Supplier"
			)
			if party_type == "Customer":
				fields = [
					"customer_name",
					"territory",
					"customer_group",
					"customer_primary_contact",
					"default_currency",
				]
			elif party_type == "Supplier":
				fields = ["supplier_name", "supplier_group", "default_currency"]
			else:
				fields = ["name"]

			self.party_details[party] = frappe.db.get_value(
				party_type, party, fields, as_dict=True
			) or {}

		return self.party_details[party]

	def set_party_details(self, row):
		if not row.party:
			return
		party_details = self.get_party_details(row.party) or {}
		row.update(party_details)

		if self.filters.get("in_party_currency"):
			# Display in Party's Billing Currency (default_currency on party master or account currency)
			row.currency = (
				party_details.get("default_currency")
				or row.account_currency
				or self.company_currency
			)
		else:
			# Always display in Company Currency (INR)
			row.currency = self.company_currency