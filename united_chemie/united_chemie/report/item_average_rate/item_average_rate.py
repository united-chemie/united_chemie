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
	data = format_rows(rows, periods, filters)
	return get_columns(periods, filters), data, None, get_chart_data(data, filters)


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
			pri.warehouse,
			pr.posting_date,
			pri.qty,
			pri.base_amount.as_("amount"),
			pri.base_rate.as_("rate"),
			pri.landed_cost_voucher_amount.as_("landed_cost_amount"),
			pri.valuation_rate,
		)
		.where((pr.docstatus == 1) & (pr.company == filters.company))
		.where(pr.posting_date.between(periods[0][0], periods[-1][1]))
		.where(pri.qty != 0)
	)
	query = apply_item_filters(query, item, pri, filters)
	query = apply_date_filters(query, pr.posting_date, filters)
	if filters.get("warehouse"):
		query = query.where(pri.warehouse == filters.warehouse)
	return query.run(as_dict=True)


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
			sed.t_warehouse.as_("warehouse"),
			se.posting_date,
			sed.qty,
			sed.amount,
			sed.basic_rate.as_("rate"),
			sed.valuation_rate,
		)
		.where((se.docstatus == 1) & (se.company == filters.company))
		.where((se.purpose == "Manufacture") & (sed.t_warehouse.isnotnull()))
		.where(se.posting_date.between(periods[0][0], periods[-1][1]))
		.where(sed.qty != 0)
	)
	query = apply_item_filters(query, item, sed, filters)
	query = apply_date_filters(query, se.posting_date, filters)
	if filters.get("warehouse"):
		query = query.where(sed.t_warehouse == filters.warehouse)
	return query.run(as_dict=True)


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


def format_rows(rows, periods=None, filters=None):
	# When called with raw rows, make one item row and populate each fiscal period.
	if periods is None:
		return rows

	filters = filters or {}
	group_by_warehouse = bool(
		filters.get("filter_by_warehouse")
		or filters.get("show_warehouse")
		or filters.get("warehouse_filter")
		or filters.get("warehouse")
	)

	data = {}
	for source_row in rows:
		warehouse = source_row.get("warehouse") or ""
		if group_by_warehouse:
			key = (source_row.item_code, source_row.item_group, warehouse)
		else:
			key = (source_row.item_code, source_row.item_group)

		if key not in data:
			row_dict = frappe._dict(
				item_code=source_row.item_code,
				item_name=source_row.item_name,
				item_group=source_row.item_group,
				qty=0,
				amount=0,
				landed_cost_amount=0,
				high_rate=None,
				high_rate_landed_cost=None,
				low_rate=None,
				low_rate_landed_cost=None,
			)
			if group_by_warehouse:
				row_dict.warehouse = warehouse

			for index in range(len(periods)):
				row_dict[f"period_{index}_qty"] = 0
				row_dict[f"period_{index}_amount"] = 0
				row_dict[f"period_{index}_landed_cost_amount"] = 0

			data[key] = row_dict

		row = data[key]
		qty = flt(source_row.qty)
		amount = flt(source_row.amount)
		rate = flt(source_row.rate)
		landed_cost_amount = flt(source_row.get("landed_cost_amount"))

		landed_rate = flt(source_row.get("valuation_rate"))
		if not landed_rate:
			landed_rate = (amount + landed_cost_amount) / qty if qty else rate

		row.qty += qty
		row.amount += amount
		row.landed_cost_amount += landed_cost_amount

		row.high_rate = rate if row.high_rate is None else max(row.high_rate, rate)
		row.low_rate = rate if row.low_rate is None else min(row.low_rate, rate)

		row.high_rate_landed_cost = (
			landed_rate if row.high_rate_landed_cost is None else max(row.high_rate_landed_cost, landed_rate)
		)
		row.low_rate_landed_cost = (
			landed_rate if row.low_rate_landed_cost is None else min(row.low_rate_landed_cost, landed_rate)
		)

		for index, (start_date, end_date) in enumerate(periods):
			if getdate(start_date) <= getdate(source_row.posting_date) <= getdate(end_date):
				row[f"period_{index}_qty"] += qty
				row[f"period_{index}_amount"] += amount
				row[f"period_{index}_landed_cost_amount"] += landed_cost_amount
				break

	for row in data.values():
		row["average_rate"] = flt(row.amount) / flt(row.qty) if flt(row.qty) else 0
		row["average_rate_landed_cost"] = (
			(flt(row.amount) + flt(row.landed_cost_amount)) / flt(row.qty) if flt(row.qty) else 0
		)
		if row.high_rate is None:
			row.high_rate = 0
		if row.low_rate is None:
			row.low_rate = 0
		if row.high_rate_landed_cost is None:
			row.high_rate_landed_cost = 0
		if row.low_rate_landed_cost is None:
			row.low_rate_landed_cost = 0

	if group_by_warehouse:
		return sorted(data.values(), key=lambda r: (r.item_code, r.get("warehouse") or ""))
	return sorted(data.values(), key=lambda r: r.item_code)


def get_chart_data(data, filters):
	"""Show the ten items with the highest total inward/production amount."""
	if not data:
		return None

	top_items = sorted(data, key=lambda row: flt(row.amount), reverse=True)[:10]
	labels = [
		f"{row.item_name or row.item_code} ({row.warehouse})"
		if row.get("warehouse")
		else (row.item_name or row.item_code)
		for row in top_items
	]
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


def get_columns(periods, filters=None):
	filters = filters or {}
	group_by_warehouse = bool(
		filters.get("filter_by_warehouse")
		or filters.get("show_warehouse")
		or filters.get("warehouse_filter")
		or filters.get("warehouse")
	)

	columns = [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
	]

	if group_by_warehouse:
		columns.append(
			{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 140}
		)

	for index, (start_date, end_date) in enumerate(periods):
		label = get_period_label(start_date, end_date)
		columns.extend(
			[
				{"label": _("{0} (Qty)").format(label), "fieldname": f"period_{index}_qty", "fieldtype": "Float", "width": 115, "convertible": "qty"},
				{"label": _("{0} (Amt)").format(label), "fieldname": f"period_{index}_amount", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 125},
				{"label": _("{0} (Landed Cost Amt)").format(label), "fieldname": f"period_{index}_landed_cost_amount", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 140},
			]
		)

	columns.extend(
		[
			{"label": _("Total Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 115, "convertible": "qty"},
			{"label": _("Total Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 135},
			{"label": _("Landed Cost Amount"), "fieldname": "landed_cost_amount", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 140},
			{"label": _("Average Rate"), "fieldname": "average_rate", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 130},
			{"label": _("Average Rate Landed Cost"), "fieldname": "average_rate_landed_cost", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 150},
			{"label": _("High Rate"), "fieldname": "high_rate", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 120},
			{"label": _("High Rate Landed Cost"), "fieldname": "high_rate_landed_cost", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 145},
			{"label": _("Low Rate"), "fieldname": "low_rate", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 120},
			{"label": _("Low Rate Landed Cost"), "fieldname": "low_rate_landed_cost", "fieldtype": "Currency", "options": "Company:company:default_currency", "width": 145},
		]
	)
	return columns


def get_period_label(start_date, end_date):
	start_date, end_date = getdate(start_date), getdate(end_date)
	if start_date.month == end_date.month:
		return start_date.strftime("%b")
	return f"{start_date.strftime('%b')}-{end_date.strftime('%b')}"