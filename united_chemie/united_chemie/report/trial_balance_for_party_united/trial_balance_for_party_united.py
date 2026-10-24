# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt

from erpnext.accounts.report.general_ledger.general_ledger import get_accounts_with_children
from erpnext.accounts.report.trial_balance.trial_balance import validate_filters
from erpnext.accounts.utils import get_currency_precision


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	show_party_name = is_party_name_visible(filters)
	show_foreign_currency = cint(filters.get("show_foreign_currency")) and filters.get("party_type") in (
		"Customer",
		"Supplier",
	)

	columns = get_columns(filters, show_party_name, show_foreign_currency)
	data = get_data(filters, show_party_name, show_foreign_currency)

	return columns, data


def get_data(filters, show_party_name, show_foreign_currency=False):
	if filters.get("party_type") in ("Customer", "Supplier", "Employee", "Member"):
		party_name_field = "{}_name".format(frappe.scrub(filters.get("party_type")))
	elif filters.get("party_type") == "Shareholder":
		party_name_field = "title"
	else:
		party_name_field = "name"

	party_filters = {"name": filters.get("party")} if filters.get("party") else {}
	party_fields = ["name", party_name_field]
	if show_foreign_currency:
		party_fields.append("default_currency")

	parties = frappe.get_all(
		filters.get("party_type"),
		fields=party_fields,
		filters=party_filters,
		order_by="name",
	)

	account_filter = []
	if filters.get("account"):
		account_filter = get_accounts_with_children(filters.get("account"))

	company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	precision = get_currency_precision()
	opening_balances = get_opening_balances(filters, account_filter)
	balances_within_period = get_balances_within_period(filters, account_filter)
	if show_foreign_currency:
		opening_balances_fc = get_opening_balances(filters, account_filter, in_account_currency=True)
		balances_within_period_fc = get_balances_within_period(
			filters, account_filter, in_account_currency=True
		)

	data = []
	# total_debit, total_credit = 0, 0
	total_row = frappe._dict(
		{
			"opening_debit": 0,
			"opening_credit": 0,
			"debit": 0,
			"credit": 0,
			"closing_debit": 0,
			"closing_credit": 0,
		}
	)
	for party in parties:
		row = {"party": party.name}
		if show_party_name:
			row["party_name"] = party.get(party_name_field)

		# opening
		opening_debit, opening_credit = opening_balances.get(party.name, [0, 0])
		opening_debit, opening_credit = flt(opening_debit, precision), flt(opening_credit, precision)
		row.update({"opening_debit": opening_debit, "opening_credit": opening_credit})

		# within period
		debit, credit = balances_within_period.get(party.name, [0, 0])
		debit, credit = flt(debit, precision), flt(credit, precision)
		row.update({"debit": debit, "credit": credit})

		# closing
		closing_debit, closing_credit = toggle_debit_credit(opening_debit + debit, opening_credit + credit)
		closing_debit, closing_credit = flt(closing_debit, precision), flt(closing_credit, precision)
		row.update({"closing_debit": closing_debit, "closing_credit": closing_credit})

		row.update({"currency": company_currency})

		if show_foreign_currency:
			opening_debit_fc, opening_credit_fc = opening_balances_fc.get(party.name, [0, 0])
			opening_debit_fc = flt(opening_debit_fc, precision)
			opening_credit_fc = flt(opening_credit_fc, precision)
			debit_fc, credit_fc = balances_within_period_fc.get(party.name, [0, 0])
			debit_fc = flt(debit_fc, precision)
			credit_fc = flt(credit_fc, precision)
			closing_debit_fc, closing_credit_fc = toggle_debit_credit(
				opening_debit_fc + debit_fc, opening_credit_fc + credit_fc
			)
			row.update(
				{
					"opening_debit_fc": flt(opening_debit_fc, precision),
					"opening_credit_fc": flt(opening_credit_fc, precision),
					"debit_fc": flt(debit_fc, precision),
					"credit_fc": flt(credit_fc, precision),
					"closing_debit_fc": flt(closing_debit_fc, precision),
					"closing_credit_fc": flt(closing_credit_fc, precision),
					"fc_currency": party.default_currency or company_currency,
					# Customer/Supplier master uses default_currency as its billing currency.
					"billing_currency": party.default_currency or company_currency,
				}
			)

		has_value = False
		if opening_debit or opening_credit or debit or credit or closing_debit or closing_credit:
			has_value = True
		# Exclude zero balance parties if filter is set
		if filters.get("exclude_zero_balance_parties") and not closing_debit and not closing_credit:
			continue

		if cint(filters.show_zero_values) or has_value:
			data.append(row)
			# totals
			for col in total_row:
				total_row[col] += row.get(col)

	total_row.update(
		{"party": "'" + _("Totals") + "'", "currency": company_currency, "billing_currency": company_currency}
	)
	data.append(total_row)

	return data


def get_opening_balances(filters, account_filter=None, in_account_currency=False):
	GL_Entry = frappe.qb.DocType("GL Entry")
	debit_field = GL_Entry.debit_in_account_currency if in_account_currency else GL_Entry.debit
	credit_field = GL_Entry.credit_in_account_currency if in_account_currency else GL_Entry.credit

	query = (
		frappe.qb.from_(GL_Entry)
		.select(
			GL_Entry.party,
			Sum(debit_field).as_("opening_debit"),
			Sum(credit_field).as_("opening_credit"),
		)
		.where(
			(GL_Entry.company == filters.company)
			& (GL_Entry.is_cancelled == 0)
			& (GL_Entry.party_type == filters.party_type)
			& (GL_Entry.party != "")
			& (
				(GL_Entry.posting_date < filters.from_date)
				| ((GL_Entry.is_opening == "Yes") & (GL_Entry.posting_date <= filters.to_date))
			)
		)
		.groupby(GL_Entry.party)
	)

	if account_filter:
		query = query.where(GL_Entry.account.isin(account_filter))

	gle = query.run(as_dict=True)

	opening = frappe._dict()
	for d in gle:
		opening_debit, opening_credit = toggle_debit_credit(d.opening_debit, d.opening_credit)
		opening.setdefault(d.party, [opening_debit, opening_credit])

	return opening


def get_balances_within_period(filters, account_filter=None, in_account_currency=False):
	GL_Entry = frappe.qb.DocType("GL Entry")
	debit_field = GL_Entry.debit_in_account_currency if in_account_currency else GL_Entry.debit
	credit_field = GL_Entry.credit_in_account_currency if in_account_currency else GL_Entry.credit

	query = (
		frappe.qb.from_(GL_Entry)
		.select(
			GL_Entry.party,
			Sum(debit_field).as_("debit"),
			Sum(credit_field).as_("credit"),
		)
		.where(
			(GL_Entry.company == filters.company)
			& (GL_Entry.is_cancelled == 0)
			& (GL_Entry.party_type == filters.party_type)
			& (GL_Entry.party != "")
			& (GL_Entry.posting_date >= filters.from_date)
			& (GL_Entry.posting_date <= filters.to_date)
			& (GL_Entry.is_opening == "No")
		)
		.groupby(GL_Entry.party)
	)

	if account_filter:
		query = query.where(GL_Entry.account.isin(account_filter))

	gle = query.run(as_dict=True)

	balances_within_period = frappe._dict()
	for d in gle:
		balances_within_period.setdefault(d.party, [d.debit, d.credit])

	return balances_within_period


def toggle_debit_credit(debit, credit):
	if flt(debit) > flt(credit):
		debit = flt(debit) - flt(credit)
		credit = 0.0
	else:
		credit = flt(credit) - flt(debit)
		debit = 0.0

	return debit, credit


def get_columns(filters, show_party_name, show_foreign_currency=False):
	columns = [
		{
			"fieldname": "party",
			"label": _(filters.party_type),
			"fieldtype": "Link",
			"options": filters.party_type,
			"width": 200,
		},
		{
			"fieldname": "opening_debit",
			"label": _("Opening (Dr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "opening_credit",
			"label": _("Opening (Cr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "debit",
			"label": _("Debit"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "credit",
			"label": _("Credit"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "closing_debit",
			"label": _("Closing (Dr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "closing_credit",
			"label": _("Closing (Cr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]

	if show_party_name:
		columns.insert(
			1,
			{
				"fieldname": "party_name",
				"label": _(filters.party_type) + " Name",
				"fieldtype": "Data",
				"width": 200,
			},
		)

	if show_foreign_currency:
		columns.insert(
			2 if show_party_name else 1,
			{
				"fieldname": "billing_currency",
				"label": _("Billing Currency"),
				"fieldtype": "Link",
				"options": "Currency",
				"width": 120,
			},
		)
		fc_columns = [
			("opening_debit_fc", _("Opening (Dr) FC")),
			("opening_credit_fc", _("Opening (Cr) FC")),
			("debit_fc", _("Debit FC")),
			("credit_fc", _("Credit FC")),
			("closing_debit_fc", _("Closing (Dr) FC")),
			("closing_credit_fc", _("Closing (Cr) FC")),
		]
		for fieldname, label in fc_columns:
			columns.append(
				{
					"fieldname": fieldname,
					"label": label,
					"fieldtype": "Currency",
					"options": "fc_currency",
					"width": 130,
				}
			)
		columns.append(
			{
				"fieldname": "fc_currency",
				"label": _("FC Currency"),
				"fieldtype": "Link",
				"options": "Currency",
				"hidden": 1,
			}
		)

	return columns


def is_party_name_visible(filters):
	show_party_name = False

	if filters.get("party_type") in ["Customer", "Supplier"]:
		if filters.get("party_type") == "Customer":
			party_naming_by = frappe.db.get_single_value("Selling Settings", "cust_master_name")
		else:
			party_naming_by = frappe.db.get_single_value("Buying Settings", "supp_master_name")

		if party_naming_by == "Naming Series":
			show_party_name = True
	else:
		show_party_name = True

	return show_party_name