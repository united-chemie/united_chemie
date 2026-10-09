"""Delivery Note batch genealogy.

Follows real incoming Stock Ledger Entries and the source rows of Stock
Entries.  It never derives a relationship from a BOM.
"""

import frappe
from frappe import _


MAX_DEPTH = 20
# Keep one unusually branching Delivery Note from blocking the user interface.
# Users can open any displayed Stock Entry and continue from the linked source.
MAX_TRACE_STEPS = 18


@frappe.whitelist()
def get_delivery_trace(delivery_note):
	if not frappe.has_permission("Delivery Note", "read", delivery_note):
		frappe.throw(_("Not permitted to read this Delivery Note"), frappe.PermissionError)
	if not frappe.has_permission("Stock Ledger Entry", "read"):
		frappe.throw(_("Not permitted to read Stock Ledger Entry"), frappe.PermissionError)

	doc = frappe.get_doc("Delivery Note", delivery_note)
	if doc.docstatus != 1:
		frappe.throw(_("Select a submitted Delivery Note"))

	tracer = DeliveryBatchTracer(doc)
	return tracer.trace()


@frappe.whitelist()
def get_branch_trace(item_code, batch_no, serial_no, reference_doctype, reference_name):
	"""Load the next segment of one branch without rebuilding the whole tree."""
	if not frappe.has_permission("Stock Ledger Entry", "read"):
		frappe.throw(_("Not permitted to read Stock Ledger Entry"), frappe.PermissionError)
	if not frappe.has_permission(reference_doctype, "read", reference_name):
		frappe.throw(_("Not permitted to read the source document"), frappe.PermissionError)
	doc = frappe.get_doc(reference_doctype, reference_name)
	tracer = DeliveryBatchTracer(doc)
	container = {"children": []}
	tracer.add_source(container, item_code, batch_no or None, serial_no or None, doc, visited=set())
	return container


class DeliveryBatchTracer:
	def __init__(self, delivery_note):
		self.delivery_note = delivery_note
		self.source_cache = {}
		self.stock_entry_values = {}
		self.trace_steps = 0

	def trace(self):
		root = self.node(
			"Delivery Note: {0}".format(self.delivery_note.name),
			"Delivery Note", self.delivery_note.name,
			subtitle=self.delivery_note.customer,
		)
		for item in self.delivery_note.items:
			batches = frappe.get_all(
				"Serial and Batch Entry",
				filters={"parent": item.serial_and_batch_bundle},
				fields=["batch_no", "serial_no", "qty"],
				order_by="idx",
			)
			if not batches:
				batches = [frappe._dict(batch_no=item.batch_no, serial_no=None, qty=item.qty)]
			for batch in batches:
				item_node = self.node(
					"Item: {0}".format(item.item_code), "Item", item.item_code,
					subtitle="Qty: {0}".format(batch.qty or item.qty),
					rate=item.rate,
				)
				root["children"].append(item_node)
				if not batch.batch_no and not batch.serial_no:
					item_node["children"].append(self.note("No serial/batch is available for this Delivery Note item."))
					continue
				tracking = self.node(
					"Batch: {0}".format(batch.batch_no) if batch.batch_no else "Serial: {0}".format(batch.serial_no),
					"Batch" if batch.batch_no else "Serial No", batch.batch_no or batch.serial_no,
					subtitle="Delivered Qty: {0}".format(batch.qty or item.qty),
				)
				item_node["children"].append(tracking)
				self.add_source(tracking, item.item_code, batch.batch_no, batch.serial_no, doc=self.delivery_note, visited=set())
		return root

	def add_source(self, parent, item_code, batch_no, serial_no, doc, visited, depth=0):
		if depth >= MAX_DEPTH:
			parent["children"].append(self.note("Trace stopped: maximum depth reached."))
			return
		if self.trace_steps >= MAX_TRACE_STEPS:
			parent["children"].append(
				self.note(
					"This branch has more transactions. Select Continue Trace to load the next part.",
					continue_args={
						"item_code": item_code, "batch_no": batch_no, "serial_no": serial_no,
						"reference_doctype": doc.doctype, "reference_name": doc.name,
					},
				)
			)
			return
		self.trace_steps += 1
		source = self.find_incoming(item_code, batch_no, serial_no, doc.posting_date, doc.posting_time, doc.doctype, doc.name)
		if not source:
			parent["children"].append(self.note("No earlier In Qty transaction found for this batch/serial."))
			return

		key = (source.name, item_code, batch_no, serial_no)
		if key in visited:
			parent["children"].append(self.note("Trace stopped: repeated transaction."))
			return
		visited = visited | {key}

		if source.voucher_type != "Stock Entry":
			parent["children"].append(self.node(
				"In Qty: {0} {1}".format(source.voucher_type, source.voucher_no),
				source.voucher_type, source.voucher_no,
				subtitle="Qty: {0} | {1}".format(source.actual_qty, source.posting_date),
			))
			return

		purpose = frappe.db.get_value("Stock Entry", source.voucher_no, "purpose")
		amount, currency = self.stock_entry_amount(source.voucher_no)
		stock_entry = self.node(
			"In Qty Stock Entry: {0}".format(source.voucher_no), "Stock Entry", source.voucher_no,
			subtitle="{0} | Qty: {1} | {2}".format(purpose, source.actual_qty, source.posting_date),
			amount=amount, currency=currency,
		)
		parent["children"].append(stock_entry)
		if purpose == "Manufacture":
			stock_entry["status"] = "Manufacture reached"
			return

		inputs = self.stock_entry_inputs(source.voucher_no)
		if not inputs:
			stock_entry["children"].append(self.note("No consumed item/batch is available on this Stock Entry."))
			return
		stock_entry_doc = frappe.get_doc("Stock Entry", source.voucher_no)
		for input_row in inputs:
			input_node = self.node(
				"Consumed Item: {0}".format(input_row.item_code), "Item", input_row.item_code,
				subtitle="Batch: {0} | Qty: {1}".format(input_row.batch_no or "Not tracked", input_row.qty),
				batch_no=input_row.batch_no, rate=input_row.basic_rate,
			)
			stock_entry["children"].append(input_node)
			if not input_row.batch_no and not input_row.serial_no:
				input_node["children"].append(self.note("This consumed row has no serial/batch; it cannot be traced exactly."))
				continue
			self.add_source(
				input_node, input_row.item_code, input_row.batch_no, input_row.serial_no,
				stock_entry_doc, visited, depth + 1,
			)

	def find_incoming(self, item_code, batch_no, serial_no, posting_date, posting_time, voucher_type, voucher_no):
		key = (item_code, batch_no, serial_no, posting_date, posting_time, voucher_type, voucher_no)
		if key in self.source_cache:
			return self.source_cache[key]
		tracking_field = "serial_no" if serial_no else "batch_no"
		tracking_value = serial_no or batch_no
		values = {
			"item_code": item_code, "serial_no": serial_no, "batch_no": batch_no,
			"posting_date": posting_date, "posting_time": posting_time,
			"voucher_type": voucher_type, "voucher_no": voucher_no,
		}
		rows = frappe.db.sql(
			"""SELECT sle.name, sle.voucher_type, sle.voucher_no, sle.actual_qty, sle.posting_date, sle.posting_time
			FROM `tabSerial and Batch Entry` sbe
			INNER JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sbe.parent
			WHERE sbe.{tracking_field} = %(tracking_value)s
			AND sle.is_cancelled = 0 AND sle.actual_qty > 0 AND sle.item_code = %(item_code)s
			AND (sle.posting_date < %(posting_date)s OR (sle.posting_date = %(posting_date)s AND sle.posting_time < %(posting_time)s))
			AND NOT (sle.voucher_type = %(voucher_type)s AND sle.voucher_no = %(voucher_no)s)
			ORDER BY sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC LIMIT 1""".format(tracking_field=tracking_field),
			values | {"tracking_value": tracking_value}, as_dict=True,
		)
		# Pre-v16 data can have a batch directly on SLE without a bundle.
		if not rows and batch_no:
			rows = frappe.db.sql(
				"""SELECT name, voucher_type, voucher_no, actual_qty, posting_date, posting_time
				FROM `tabStock Ledger Entry` WHERE is_cancelled = 0 AND actual_qty > 0
				AND item_code = %(item_code)s AND batch_no = %(batch_no)s
				AND (posting_date < %(posting_date)s OR (posting_date = %(posting_date)s AND posting_time < %(posting_time)s))
				ORDER BY posting_date DESC, posting_time DESC, creation DESC LIMIT 1""",
				values, as_dict=True,
			)
		self.source_cache[key] = rows[0] if rows else None
		return self.source_cache[key]

	def stock_entry_inputs(self, stock_entry):
		rows = frappe.db.sql(
			"""SELECT sed.item_code, sed.qty, sed.basic_rate, COALESCE(sbe.batch_no, sed.batch_no) AS batch_no, sbe.serial_no
			FROM `tabStock Entry Detail` sed
			LEFT JOIN `tabSerial and Batch Entry` sbe ON sbe.parent = sed.serial_and_batch_bundle
			WHERE sed.parent = %s AND IFNULL(sed.s_warehouse, '') != ''
			ORDER BY sed.idx, sbe.idx""",
			stock_entry, as_dict=True,
		)
		# A Stock Entry can contain repeated untracked rows for the same item.
		# They represent one trace stop, so show a single consolidated branch.
		grouped = {}
		for row in rows:
			key = (row.item_code, row.batch_no, row.serial_no)
			if key not in grouped:
				grouped[key] = frappe._dict(row)
			else:
				grouped[key].qty += row.qty
		return list(grouped.values())

	def stock_entry_amount(self, stock_entry):
		if stock_entry not in self.stock_entry_values:
			values = frappe.db.get_value(
				"Stock Entry", stock_entry, ["total_incoming_value", "company"], as_dict=True
			) or {}
			currency = frappe.db.get_value("Company", values.get("company"), "default_currency")
			self.stock_entry_values[stock_entry] = (values.get("total_incoming_value") or 0, currency)
		return self.stock_entry_values[stock_entry]

	def node(self, title, doctype=None, name=None, subtitle=None, batch_no=None, amount=None, currency=None, rate=None):
		return {
			"title": title, "doctype": doctype, "name": name, "subtitle": subtitle,
			"batch_no": batch_no, "children": [],
			"amount": amount, "currency": currency,
			"rate": rate,
		}

	def note(self, title, continue_args=None):
		return {"title": title, "note": 1, "continue_args": continue_args, "children": []}