from erpnext.selling.doctype.sales_order.sales_order import SalesOrder as _SalesOrder
import frappe

class CustomSalesOrder(_SalesOrder):
	def validate_party_address_and_contact(self):
		party_type, party = self.get_party()

		if not (party_type and party):
			return

		if party_type == "Customer":
			billing_address, shipping_address = (
				self.get("customer_address"),
				self.get("shipping_address_name"),
			)
			self.validate_party_address(party, party_type, billing_address, shipping_address)
		elif party_type == "Supplier":
			billing_address = self.get("supplier_address")
			self.validate_party_address(party, party_type, billing_address)

		self.validate_party_contact(party, party_type)
  
	def validate_party_address(self, party, party_type, billing_address, shipping_address=None):
		pass
		# if billing_address or shipping_address:
		#     party_address = frappe.get_all(
		#         "Dynamic Link",
		#         {"link_doctype": party_type, "link_name": party, "parenttype": "Address"},
		#         pluck="parent",
		#     )
			# if billing_address and billing_address not in party_address:
			#     frappe.throw(_("Billing Address does not belong to the {0}").format(party))
			# elif shipping_address and shipping_address not in party_address:
			#     frappe.throw(_("Shipping Address does not belong to the {0}").format(party))

