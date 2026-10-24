# Copyright (c) 2026, United Chemie and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate
from dateutil.relativedelta import relativedelta

from erpnext.controllers.trends import get_period_date_ranges


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	periods = get_periods(filters)
	rows = get_manufacture_data(filters, periods) if filters.type == "Manufacture" else get_purchase_receipt_data(filters, periods)
	data = format_rows(rows, periods)
	return get_columns(periods), data, None, get_chart_data(data, filters)


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is required."))
	if not filters.get("period"):
		frappe.throw(_("Period is required."))
	filter_based_on = filters.get("filter_based_on", "Fiscal Year")
	if filter_based_on == "Fiscal Year" and not filters.get("fiscal_year"):
		frappe.throw(_("Fiscal Year is required."))
	if filter_based_on == "Date Range" and (not filters.get("from_date") or not filters.get("to_date")):
		frappe.throw(_("From Date and To Date are required."))
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_periods(filters):
	if filters.get("filter_based_on", "Fiscal Year") == "Fiscal Year":
		return get_period_date_ranges(filters.period, filters.fiscal_year)

	increment = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}[filters.period]
	start_date, end_date = getdate(filters.from_date), getdate(filters.to_date)
	periods = []
	while start_date <= end_date:
		period_end_date = min(start_date + relativedelta(months=increment, days=-1), end_date)
		periods.append([start_date, period_end_date])
		start_date = period_end_date + relativedelta(days=1)
	return periods


def get_purchase_receipt_data(filters, periods):
	pr = frappe.qb.DocType("Purchase Receipt")
	pri = frappe.qb.DocType("Purchase Receipt Item")
	item = frappe.qb.DocType("Item")

	query = (
		frappe.qb.from_(pr)
		.join(pri).on(pri.parent == pr.name)
		.join(item).on(item.name == pri.item_code)
		.select(
			pri.item_code,
			pri.item_name,
			item.item_group,
			pr.posting_date,
			item.last_purchase_rate,
			pri.qty,
			pri.base_amount.as_("amount"),
			pri.base_rate.as_("rate"),
		)
		.where((pr.docstatus == 1) & (pr.company == filters.company))
		.where(pr.posting_date.between(periods[0][0], periods[-1][1]))
		.where(pri.qty != 0)
	)
	query = apply_item_filters(query, item, pri, filters)
	query = apply_date_filters(query, pr.posting_date, filters)
	return format_rows(query.run(as_dict=True))


def get_manufacture_data(filters, periods):
	se = frappe.qb.DocType("Stock Entry")
	sed = frappe.qb.DocType("Stock Entry Detail")
	item = frappe.qb.DocType("Item")

	# A manufacture entry contains consumed rows and output rows. Only output rows
	# (target warehouse set) represent the manufactured item and its production cost.
	query = (
		frappe.qb.from_(se)
		.join(sed).on(sed.parent == se.name)
		.join(item).on(item.name == sed.item_code)
		.select(
			sed.item_code,
			sed.item_name,
			item.item_group,
			se.posting_date,
			sed.qty,
			sed.amount,
			sed.basic_rate.as_("rate"),
		)
		.where((se.docstatus == 1) & (se.company == filters.company))
		.where((se.purpose == "Manufacture") & (sed.t_warehouse.isnotnull()))
		.where(se.posting_date.between(periods[0][0], periods[-1][1]))
		.where(sed.qty != 0)
	)
	query = apply_item_filters(query, item, sed, filters)
	query = apply_date_filters(query, se.posting_date, filters)
	return format_rows(query.run(as_dict=True))


def apply_item_filters(query, item, detail, filters):
	if filters.get("item_code"):
		query = query.where(detail.item_code == filters.item_code)
	if filters.get("item_group"):
		query = query.where(item.item_group == filters.item_group)
	return query


def apply_date_filters(query, posting_date, filters):
	if filters.get("filter_based_on") == "Date Range" and filters.get("from_date"):
		query = query.where(posting_date >= filters.from_date)
	if filters.get("filter_based_on") == "Date Range" and filters.get("to_date"):
		query = query.where(posting_date <= filters.to_date)
	return query


def format_rows(rows, periods=None):
	# When called with raw rows, make one item row and populate each fiscal period.
	if periods is None:
		return rows

	data = {}
	for source_row in rows:
		key = (source_row.item_code, source_row.item_group)
		if key not in data:
			data[key] = frappe._dict(
				item_code=source_row.item_code,
				item_name=source_row.item_name,
				item_group=source_row.item_group,
				last_purchase_rate=flt(source_row.get("last_purchase_rate")),
				qty=0,
				amount=0,
				high_rate=None,
				low_rate=None,
			)
			for index in range(len(periods)):
				data[key][f"period_{index}_qty"] = 0
				data[key][f"period_{index}_amount"] = 0

		row = data[key]
		qty, amount, rate = flt(source_row.qty), flt(source_row.amount), flt(source_row.rate)
		row.qty += qty
		row.amount += amount
		row.high_rate = rate if row.high_rate is None else max(row.high_rate, rate)
		row.low_rate = rate if row.low_rate is None else min(row.low_rate, rate)

		for index, (start_date, end_date) in enumerate(periods):
			if getdate(start_date) <= getdate(source_row.posting_date) <= getdate(end_date):
				row[f"period_{index}_qty"] += qty
				row[f"period_{index}_amount"] += amount
				break

	for row in data.values():
		row["average_rate"] = flt(row.amount) / flt(row.qty) if flt(row.qty) else 0
	return sorted(data.values(), key=lambda row: row.item_code)


def get_chart_data(data, filters):
	"""Show the ten items with the highest total inward/production amount."""
	if not data:
		return None

	top_items = sorted(data, key=lambda row: flt(row.amount), reverse=True)[:10]
	labels = [row.item_name or row.item_code for row in top_items]
	values = [flt(row.amount) for row in top_items]
	transaction_type = _("Manufacture") if filters.type == "Manufacture" else _("Purchase Receipt")

	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Total Amount"), "values": values}],
		},
		"type": "bar",
		"colors": ["#5e64ff"],
		"fieldtype": "Currency",
		"options": "currency",
		"currency": frappe.get_cached_value("Company", filters.company, "default_currency"),
		"title": _("Top 10 Items by {0} Amount").format(transaction_type),
	}


def get_columns(periods):
	columns = [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
	]

	for index, (start_date, end_date) in enumerate(periods):
		label = get_period_label(start_date, end_date)
		columns.extend(
			[
				{"label": _("{0} (Qty)").format(label), "fieldname": f"period_{index}_qty", "fieldtype": "Float", "width": 115, "convertible": "qty"},
				{"label": _("{0} (Amt)").format(label), "fieldname": f"period_{index}_amount", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 125},
			]
		)

	columns.extend(
		[
			{"label": _("Total Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 115, "convertible": "qty"},
			{"label": _("Total Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 135},
			{"label": _("Last Purchase Rate"), "fieldname": "last_purchase_rate", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 135},
			{"label": _("Average Rate"), "fieldname": "average_rate", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 130},
			{"label": _("High Rate"), "fieldname": "high_rate", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 120},
			{"label": _("Low Rate"), "fieldname": "low_rate", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 120},
		]
	)
	return columns


def get_period_label(start_date, end_date):
	start_date, end_date = getdate(start_date), getdate(end_date)
	if start_date.month == end_date.month:
		return start_date.strftime("%b")
	return f"{start_date.strftime('%b')}-{end_date.strftime('%b')}"