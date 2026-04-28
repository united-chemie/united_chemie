import frappe, erpnext
from frappe import _
from chemical.chemical.doctype.ball_mill_data_sheet.ball_mill_data_sheet import BallMillDataSheet as _BallMillDataSheet
from frappe.utils import nowtime, flt, cint, getdate, get_fullname, get_url_to_form
from erpnext.stock.doctype.item.item import get_item_defaults
from chemical.comments_api import creation_comment,status_change_comment,cancellation_comment,delete_comment


class BallMillDataSheet(_BallMillDataSheet):
	def after_insert(self):
		if self.get('create_stock_entry') == 0:
			create_stock_entry = 0
		else:
			create_stock_entry = 1
		if create_stock_entry:
			se = frappe.new_doc("Stock Entry")
			se.purpose = "Repack"
			se.company = self.company
			se.stock_entry_type = "Repack"
			se.set_posting_time = 1
			se.posting_date = self.date
			se.posting_time = self.posting_time
			se.from_ball_mill = 1
			se.cost_center = self.cost_center
			# se.branch = self.branch
			cost_center = frappe.db.get_value("Company",self.company,"cost_center")
			if hasattr(self,'send_to_party'):
				se.send_to_party = self.send_to_party
			if hasattr(self,'party_type'):
				se.party_type = self.party_type
			if hasattr(self,'party'):
				se.party = self.party

			for row in self.items:
				item = get_item_defaults(row.item_name, self.company)
				item_dict = {
					'item_code': row.item_name,
					's_warehouse': row.source_warehouse,
					'qty': row.qty,
					'basic_rate': row.basic_rate,
					't_warehouse':None,
					'uom':frappe.db.get_value("Item",row.item_name,"stock_uom"),
					'stock_uom':frappe.db.get_value("Item",self.product_name,"stock_uom"),
					'basic_amount': row.basic_amount,
					'cost_center': self.cost_center,
					'batch_no': row.batch_no,
					'concentration':row.concentration,
					'packaging_material':row.packaging_material,
					'packing_size':row.packing_size,
					'no_of_packages':row.no_of_packages,
					"use_serial_batch_fields": True
				}

				se.append('items', item_dict)
			for d in self.packaging:	
				item = get_item_defaults(self.product_name, self.company)
				item_dict = {
					'item_code': self.product_name,
					't_warehouse': d.warehouse or self.warehouse,
					's_warehouse':None,
					'uom':frappe.db.get_value("Item",self.product_name,"stock_uom"),
					'stock_uom':frappe.db.get_value("Item",self.product_name,"stock_uom"),
					'qty': d.qty,
					'packaging_material': d.packaging_material,
					'packing_size': d.packing_size,
					'no_of_packages': d.no_of_packages,
					'lot_no': d.lot_no,
					'concentration': d.concentration or self.concentration,
					'basic_rate': self.per_unit_amount,
					'valuation_rate': self.per_unit_amount,
					'basic_amount': flt(d.qty * self.per_unit_amount),
					'cost_center': self.cost_center,
					'uv_value':self.get("weighted_average_uv_value"),
					"use_serial_batch_fields": True
				}

				se.append('items', item_dict)
			
			for d in self.ball_mill_additional_cost:	
				se.append('additional_costs',{
					'expense_account':d.expense_account ,
					'description': d.description,
					'amount': flt(d.amount),
					'rate':flt(d.amount),
					'qty':1
				})

			se.save()
			self.db_set('stock_entry',se.name)
			se.flags.ignore_validate = True
    
	def on_submit(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 0:
				se.flags.ignore_validate = True
				se.submit()