import frappe
from frappe.utils import now_datetime

def validate(self,method):
	set_batch_serial_check_box(self)

def set_batch_serial_check_box(self):
	if frappe.db.get_value("Item", self.production_item, "has_batch_no") == 1:
		self.has_batch_no = 1
		self.has_serial_no = 0

def on_submit(self,method):
	set_batch_no(self)

def onload(self,method):
	set_batch_no(self)
	
def set_batch_no(self):
	if frappe.get_all("Batch", filters={'reference_name': self.name,} ):
		batch = frappe.get_all("Batch", filters={'reference_name': self.name,} )
		doc = frappe.get_doc("Work Order", self.name)
		doc.db_set("batch_no", batch[0].name)