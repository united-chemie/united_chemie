# Copyright (c) 2026, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.utils.nestedset import get_descendants_of

from erpnext.stock.report.stock_balance.stock_balance import StockBalanceReport

BASE_ITEM_GROUPS = [
	"Packing Material",
	"Power & Fuel",
	"Raw Material",
	"Stores",
	"TRADING",
]


def get_base_item_groups():
	base_groups = list(BASE_ITEM_GROUPS)
	try:
		all_groups = frappe.get_all("Item Group", pluck="name") or []
		all_groups_lower = {g.lower(): g for g in all_groups}

		resolved = []
		for bg in BASE_ITEM_GROUPS:
			bg_lower = bg.lower()
			if bg_lower in all_groups_lower:
				resolved.append(all_groups_lower[bg_lower])
			elif bg_lower + "s" in all_groups_lower:
				resolved.append(all_groups_lower[bg_lower + "s"])
			else:
				resolved.append(bg)
		return resolved
	except Exception:
		return base_groups


def get_all_allowed_item_groups():
	base_groups = get_base_item_groups()
	allowed = set()
	for bg in base_groups:
		allowed.add(bg)
		try:
			if frappe.db.exists("Item Group", bg):
				descendants = get_descendants_of("Item Group", bg, ignore_permissions=True) or []
				allowed.update(descendants)
		except Exception:
			pass
	return sorted(list(allowed))


class RMStockBalanceReport(StockBalanceReport):
	def is_warehouse_wise(self) -> bool:
		return bool(
			self.filters.get("warehouse")
			or self.filters.get("warehouse_type")
			or self.filters.get("show_warehouse_wise_stock")
		)

	def run(self):
		self.float_precision = cint(frappe.db.get_default("float_precision")) or 3

		self.inventory_dimensions = self.get_inventory_dimension_fields()
		self.prepare_opening_data_from_closing_balance()
		self.prepare_stock_ledger_entries()
		self.prepare_new_data()

		if not self.is_warehouse_wise():
			self.aggregate_by_item()

		if not self.columns:
			self.columns = self.get_columns()

		self.add_additional_uom_columns()

		return self.columns, self.data

	def get_columns(self):
		columns = super().get_columns()
		if not self.is_warehouse_wise():
			columns = [c for c in columns if c.get("fieldname") != "warehouse"]
		return columns

	def aggregate_by_item(self):
		aggregated = {}
		for row in self.data:
			key = [row.get("company"), row.get("item_code")]
			if self.filters.get("show_dimension_wise_stock"):
				for dim in self.inventory_dimensions:
					key.append(row.get(dim))
			group_key = tuple(key)

			if group_key not in aggregated:
				entry = frappe._dict(row.copy())
				entry["warehouse"] = ""
				aggregated[group_key] = entry
			else:
				agg = aggregated[group_key]
				for f in (
					"opening_qty",
					"opening_val",
					"in_qty",
					"in_val",
					"out_qty",
					"out_val",
					"bal_qty",
					"bal_val",
					"reserved_stock",
				):
					agg[f] = flt(agg.get(f, 0.0)) + flt(row.get(f, 0.0))

		for agg in aggregated.values():
			bal_qty = flt(agg.get("bal_qty"), self.float_precision)
			bal_val = flt(agg.get("bal_val"))
			if bal_qty != 0:
				agg["val_rate"] = flt(bal_val / bal_qty, self.float_precision)
			else:
				agg["val_rate"] = 0.0

		data = list(aggregated.values())
		if not self.filters.get("include_zero_stock_items"):
			data = [d for d in data if not (d.bal_qty == 0 and d.bal_val == 0)]

		self.data = data

	def apply_warehouse_filters(self, query, sle):
		query = super().apply_warehouse_filters(query, sle)
		if not self.filters.get("warehouse"):
			query = query.where(~sle.warehouse.like("%Work In Progress%"))
		return query

	def prepare_stock_ledger_entries(self):
		sle = frappe.qb.DocType("Stock Ledger Entry")
		item_table = frappe.qb.DocType("Item")
		se = frappe.qb.DocType("Stock Entry")

		query = (
			frappe.qb.from_(sle)
			.inner_join(item_table)
			.on(sle.item_code == item_table.name)
			.left_join(se)
			.on((sle.voucher_type == "Stock Entry") & (sle.voucher_no == se.name))
			.select(
				sle.item_code,
				sle.warehouse,
				sle.posting_date,
				sle.actual_qty,
				sle.valuation_rate,
				sle.company,
				sle.voucher_type,
				sle.qty_after_transaction,
				sle.stock_value_difference,
				sle.item_code.as_("name"),
				sle.voucher_no,
				sle.stock_value,
				sle.batch_no,
				sle.serial_no,
				sle.serial_and_batch_bundle,
				sle.voucher_detail_no,
				sle.is_adjustment_entry,
				item_table.has_serial_no,
				item_table.has_batch_no,
				item_table.item_group,
				item_table.stock_uom,
				item_table.item_name,
				se.purpose.as_("stock_entry_purpose"),
			)
			.where((sle.docstatus < 2) & (sle.is_cancelled == 0))
			.orderby(sle.posting_datetime)
			.orderby(sle.creation)
		)

		query = self.apply_inventory_dimensions_filters(query, sle)
		query = self.apply_warehouse_filters(query, sle)
		query = self.apply_items_filters(query, item_table)
		query = self.apply_date_filters(query, sle)

		if self.filters.get("company"):
			query = query.where(sle.company == self.filters.get("company"))

		self.sle_query = query

	def prepare_item_warehouse_map(self, item_warehouse_map, entry, group_by_key):
		qty_dict = item_warehouse_map[group_by_key]
		for field in self.inventory_dimensions:
			qty_dict[field] = entry.get(field)

		qty_diff = flt(entry.actual_qty)
		value_diff = flt(entry.stock_value_difference)

		if entry.posting_date < self.from_date or entry.voucher_no in self.opening_vouchers.get(
			entry.voucher_type, []
		):
			qty_dict.opening_qty += qty_diff
			qty_dict.opening_val += value_diff

		elif entry.posting_date >= self.from_date and entry.posting_date <= self.to_date:
			is_valid_in = (entry.voucher_type == "Purchase Receipt")
			is_valid_out = (
				entry.voucher_type == "Stock Entry"
				and entry.get("stock_entry_purpose") in ("Material Transfer for Manufacture", "Material Issue")
			)

			if flt(qty_diff, self.float_precision) >= 0:
				if is_valid_in:
					qty_dict.in_qty += qty_diff
					qty_dict.in_val += value_diff
			else:
				if is_valid_out:
					qty_dict.out_qty += abs(qty_diff)
					qty_dict.out_val += abs(value_diff)

		qty_dict.val_rate = entry.valuation_rate
		qty_dict.bal_qty = qty_dict.opening_qty + qty_dict.in_qty - qty_dict.out_qty
		qty_dict.bal_val = qty_dict.opening_val + qty_dict.in_val - qty_dict.out_val
		if qty_dict.bal_qty != 0:
			qty_dict.val_rate = flt(qty_dict.bal_val / qty_dict.bal_qty, self.float_precision)
		else:
			qty_dict.val_rate = 0.0

	def prepare_opening_data_from_closing_balance(self) -> None:
		super().prepare_opening_data_from_closing_balance()
		if not self.filters.get("item_group"):
			allowed_groups = set(get_all_allowed_item_groups())
			keys_to_remove = [
				key
				for key, entry in self.opening_data.items()
				if entry.get("item_group") not in allowed_groups
			]
			for key in keys_to_remove:
				del self.opening_data[key]

	def apply_items_filters(self, query, item_table):
		if item_group := self.filters.get("item_group"):
			children = get_descendants_of("Item Group", item_group, ignore_permissions=True) or []
			query = query.where(item_table.item_group.isin([*children, item_group]))
		else:
			allowed_groups = get_all_allowed_item_groups()
			query = query.where(item_table.item_group.isin(allowed_groups))

		if item_codes := self.filters.get("item_code"):
			if isinstance(item_codes, str):
				item_codes = [item_codes]
			query = query.where(item_table.name.isin(item_codes))

		if brand := self.filters.get("brand"):
			query = query.where(item_table.brand == brand)

		return query

	def get_itemwise_conversion_factor(self):
		items = [d.item_code for d in self.data]
		if not items:
			return frappe._dict({})

		table = frappe.qb.DocType("UOM Conversion Detail")
		query = (
			frappe.qb.from_(table)
			.select(table.conversion_factor, table.parent)
			.where((table.parenttype == "Item") & (table.uom == self.filters.include_uom))
			.where(table.parent.isin(items))
		)
		return frappe._dict(query.run(as_dict=False))

	def get_variant_values_for(self):
		attribute_map = {}
		items = [d.item_code for d in self.data]
		if not items:
			return attribute_map

		filters = {"parent": ("in", items)}
		attribute_info = frappe.get_all(
			"Item Variant Attribute",
			fields=["parent", "attribute", "attribute_value"],
			filters=filters,
		)
		for attr in attribute_info:
			attribute_map.setdefault(attr["parent"], {})
			attribute_map[attr["parent"]].update({attr["attribute"]: attr["attribute_value"]})
		return attribute_map


def execute(filters=None):
	if not filters:
		filters = {}

	if isinstance(filters, dict):
		filters = frappe._dict(filters)

	allowed_groups = set(get_all_allowed_item_groups())

	selected_group = filters.get("item_group")
	if selected_group:
		if selected_group not in allowed_groups:
			frappe.throw(
				_("Item Group must be one of: {0} (or their sub-groups)").format(
					", ".join(BASE_ITEM_GROUPS)
				)
			)

	return RMStockBalanceReport(filters).run()


@frappe.whitelist()
def get_item_group_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	allowed_groups = get_all_allowed_item_groups()

	matching_groups = [g for g in allowed_groups if not txt or txt.lower() in g.lower()]
	matching_groups.sort()

	start_idx = int(start or 0)
	page_length = int(page_len or 20)
	paged_groups = matching_groups[start_idx : start_idx + page_length]

	if as_dict:
		return [{"name": g} for g in paged_groups]
	return [(g,) for g in paged_groups]


@frappe.whitelist()
def get_rm_items(txt=None, item_group=None):
	if item_group:
		allowed_groups = [item_group]
		if frappe.db.exists("Item Group", item_group):
			descendants = get_descendants_of("Item Group", item_group, ignore_permissions=True) or []
			allowed_groups.extend(descendants)
	else:
		allowed_groups = get_all_allowed_item_groups()

	from erpnext.controllers.queries import item_query

	data = item_query(
		doctype="Item",
		txt=txt or "",
		searchfield="name",
		start=0,
		page_len=20,
		filters={"item_group": ["in", allowed_groups], "is_stock_item": 1},
		as_dict=True,
	)

	return [
		{"value": d.get("name"), "description": d.get("item_name") or d.get("description")}
		for d in (data or [])
	]