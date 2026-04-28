import frappe
from frappe.utils import cint
from frappe.utils import get_link_to_form
 
def custom_create_quality_inspection_entry(self):
    for inspection_item in self.items:
        item = frappe.get_doc("Item", inspection_item.item_code)
        if self.purpose == "Manufacture" or (self.purpose == "Repack" and cint(self.from_ball_mill) == 1):
            if (
                item.inspection_required_after_stock_entry
                and inspection_item.is_finished_item
            ):
                if inspection_item.t_warehouse:
                    quality_inspection = frappe.new_doc("Quality Inspection")
                    quality_inspection.naming_series = "MAT-IS-.YYYY.-"
                    quality_inspection.item_code = inspection_item.item_code
                    quality_inspection.ref_itm = inspection_item.name
                    quality_inspection.inspection_type = "Outgoing"
                    quality_inspection.reference_type = "Stock Entry"
                    quality_inspection.reference_name = self.name
                    quality_inspection.sample_size = inspection_item.qty
                    quality_inspection.description = inspection_item.description
                    quality_inspection.remarks = self.remarks
                    quality_inspection.inspected_by = self.modified_by
                    quality_inspection.sample_size_uom = inspection_item.uom
                    quality_inspection.batch_no = inspection_item.batch_no
                    quality_inspection.quality_inspection_template = (
                        frappe.db.get_value(
                            "Item",
                            inspection_item.item_code,
                            "quality_inspection_template",
                        )
                    )
                    try:
                        quality_inspection.save(ignore_permissions=True)
                    except Exception as e:
                        frappe.throw(str(e))
                    else:
                        frappe.db.set_value(
                            inspection_item.doctype,
                            inspection_item.name,
                            "quality_inspection",
                            quality_inspection.name,
                        )
                        frappe.msgprint(
                            "Quality Inspection {} is Created".format(
                                get_link_to_form(
                                    "Quality Inspection", quality_inspection.name
                                )
                            )
                        )
