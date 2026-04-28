# from collections import defaultdict
# import frappe
# from frappe import _, scrub
# from frappe.utils import cint, flt
# from erpnext.controllers.queries import get_match_cond
# from erpnext.stock.utils import get_incoming_rate


# def execute(filters=None):
#     if not filters:
#         filters = frappe._dict()
#     filters.currency = frappe.get_cached_value("Company", filters.company, "default_currency")
#     # frappe.throw(str(filters.currency))
#     gross_profit_data = GrossProfitGenerator(filters)
#     data = []
    
#     # --- Purchase Invoice based indirect expenses ---
#     indirect_expence_data_account_wise = frappe.db.sql("""
#         SELECT
#             pii.indirect_expense_for_sales AS sales_invoice,
#             pii.expense_account,
#             SUM(pii.net_amount) AS expense_amount
#         FROM
#             `tabPurchase Invoice Item` AS pii
#         INNER JOIN `tabPurchase Invoice` AS pi ON pii.parent = pi.name AND pi.docstatus = 1
#         INNER JOIN `tabSales Invoice` AS si ON pii.indirect_expense_for_sales = si.name AND si.docstatus = 1
#         WHERE
#             pii.indirect_expense_for_sales IS NOT NULL
#             AND pii.indirect_expense_for_sales != ''
#         GROUP BY
#             pii.indirect_expense_for_sales,
#             pii.expense_account
#     """, as_dict=1)
    
#     sales_invoice_expenses = defaultdict(list)
#     expence_accounts = set()
#     for row in indirect_expence_data_account_wise:
#         company = frappe.get_value("Account", row["expense_account"], "company")
#         if company == filters.company:
#             expence_accounts.add(row["expense_account"])
#     expence_accounts = sorted(list(expence_accounts))
#     expence_head_columns = [
#         {"label": account, "fieldname": scrub(account), "fieldtype": "Currency", "width": 120}
#         for account in expence_accounts
#     ]

#     for row in indirect_expence_data_account_wise:
#         sales_invoice_expenses[row["sales_invoice"]].append({
#             "expense_account": row["expense_account"],
#             "expense_amount": row["expense_amount"]
#         })
    
#     # --- Journal Entry based charges ---
#     loading_unloading_charges = get_loading_unloading_charges()
#     foreign_bank_charges_combined = get_foreign_bank_charges_combined()
    
#     # --- Columns setup ---
#     group_wise_columns = frappe._dict({
#         "invoice": [
#             "invoice_or_item", "posting_date", "warehouse", "customer", "description", "final_destination", "shipping_terms", 
#             "customer_group", "item_group", "qty", "currency","company_currency","rate", "total", "conversion_rate", 
#             "base_amount","base_rate",  "buying_rate", "buying_amount", "gross_profit", "gross_profit_percent",
#             "no_of_packages", "packaging_material", "debit_in_account_currency", "foreign_bank_charges_combined",
#             "indirect_expence", "per_kg_indirect_expense", "buying_plus_indirect",
#             "per_kg_cost"
#         ],
#     })
    
#     # columns = get_columns(group_wise_columns, filters)
#     columns = get_columns(group_wise_columns, filters, expence_head_columns)
#     # columns.extend(expence_head_columns)
    
#     # --- Data fetch ---
#     if filters.group_by == "Invoice":
#         get_data_when_grouped_by_invoice(columns, gross_profit_data, filters, group_wise_columns, data)
#     else:
#         get_data_when_not_grouped_by_invoice(gross_profit_data, filters, group_wise_columns, data)
    
#     chart_data = get_chart_data(data, filters)
    
#     # --- Process data rows ---
#     # Accounts that are in foreign currency and need conversion
#     foreign_currency_accounts = {scrub("Freight Outward - UCPL")}

#     for row in data:
#         sales_invoice_name = None
        
#         if isinstance(row, dict):
#             sales_invoice_name = row.get('sales_invoice') or row.get('invoice_or_item') or row.get('parent_invoice')
        
#         if sales_invoice_name:
#             expence_accounts_for_invoice = sales_invoice_expenses.get(sales_invoice_name, [])
#             for expense in expence_accounts_for_invoice:
#                 if isinstance(row, dict):
#                     row[scrub(expense["expense_account"])] = expense["expense_amount"]
        
#         if isinstance(row, dict):
#             # Set Loading Unloading Charges
#             row['debit_in_account_currency'] = loading_unloading_charges.get(sales_invoice_name, 0.0)

#             # Set Foreign Bank Charges (renamed to Foreign Bank Charges INR)
#             row['foreign_bank_charges_combined'] = foreign_bank_charges_combined.get(sales_invoice_name, 0.0)

#             # Prepare list of expense fields to sum
#             expense_fields_to_sum = [
#                 'debit_in_account_currency',
#                 'foreign_bank_charges_combined',
#                 scrub("Export Bank Charges - UCPL"),
#                 scrub("Export Expense - UCPL"),
#                 scrub("Freight Outward - UCPL")
#             ]
            
#             # Calculate total indirect expense in company currency
#             total_indirect_expence = 0.0
#             for field in expense_fields_to_sum:
#                 value = flt(row.get(field, 0.0))

#                 # Convert if account is in foreign currency
#                 if field in foreign_currency_accounts and row.get("conversion_rate"):
#                     value = value * flt(row["conversion_rate"])

#                 total_indirect_expence += value

#             row["indirect_expence"] = total_indirect_expence
            
#             # Calculate Per Kg Indirect Expense
#             if flt(row.get("qty", 0)):
#                 row["per_kg_indirect_expense"] = flt(total_indirect_expence / flt(row["qty"]), 2)
#             else:
#                 row["per_kg_indirect_expense"] = 0.0
            
#             # Calculate Buying Amount + Indirect Expense
#             row["buying_plus_indirect"] = flt(row.get("buying_amount", 0)) + total_indirect_expence
            
#             # Calculate Per Kg Cost
#             if flt(row.get("qty", 0)):
#                 row["per_kg_cost"] = flt(row["buying_plus_indirect"] / flt(row["qty"]), 2)
#             else:
#                 row["per_kg_cost"] = 0.0

#     return columns, data, None, chart_data


# def get_loading_unloading_charges():
#     """
#     Get Loading Unloading Charges from Journal Entry
#     Logic: Journal Entry -> Journal Entry Account -> Sales Invoice
#     If Account has root_type = 'Expense', show debit value as Loading Unloading Charges
#     """
#     loading_charges_data = frappe.db.sql("""
#         SELECT 
#             jea.sales_invoice as sales_invoice,
#             SUM(jea.debit_in_account_currency) as loading_charges
#         FROM 
#             `tabJournal Entry` je
#         INNER JOIN 
#             `tabJournal Entry Account` jea ON je.name = jea.parent
#         INNER JOIN 
#             `tabAccount` acc ON jea.account = acc.name
#         WHERE 
#             je.docstatus = 1
#             AND jea.sales_invoice IS NOT NULL
#             AND jea.sales_invoice != ''
#             AND acc.root_type = 'Expense'
#             AND jea.debit_in_account_currency > 0
#         GROUP BY 
#             jea.sales_invoice
#     """, as_dict=1)
    
#     loading_charges_dict = {}
#     for row in loading_charges_data:
#         if row.sales_invoice:
#             loading_charges_dict[row.sales_invoice] = row.loading_charges
    
#     return loading_charges_dict


# def get_foreign_bank_charges_combined():
#     """
#     Get Combined Foreign Bank Charges (Foreign Currency + INR) from Journal Entry
#     Logic: Journal Entry -> Journal Entry Account -> Sales Invoice
#     If Account parent_account contains 'Bank Charge', combine both debit and debit_in_account_currency
#     """
#     bank_charges_data = frappe.db.sql("""
#         SELECT 
#             jea.sales_invoice as sales_invoice,
#             SUM(jea.debit) as bank_charges_combined
#         FROM 
#             `tabJournal Entry` je
#         INNER JOIN 
#             `tabJournal Entry Account` jea ON je.name = jea.parent
#         INNER JOIN 
#             `tabAccount` acc ON jea.account = acc.name
#         INNER JOIN 
#             `tabAccount` parent_acc ON acc.parent_account = parent_acc.name
#         WHERE 
#             je.docstatus = 1
#             AND jea.sales_invoice IS NOT NULL
#             AND jea.sales_invoice != ''
#             AND (parent_acc.name LIKE '%Bank Charge%' OR parent_acc.name LIKE '%Bank Charges%')
#             AND (jea.debit > 0 OR jea.debit > 0)
#         GROUP BY 
#             jea.sales_invoice
#     """, as_dict=1)
    
#     bank_charges_dict = {}
#     for row in bank_charges_data:
#         if row.sales_invoice:
#             bank_charges_dict[row.sales_invoice] = row.bank_charges_combined
    
#     return bank_charges_dict

# def get_chart_data(data, filters):
#     if not data:
#         return None
    
#     labels = []
#     datapoints = []

#     if filters.get("group_by") == "Invoice":
#         # Filter for main invoice rows (indent = 0)
#         invoice_data = [row for row in data if isinstance(row, dict) and row.get('indent', 1) == 0]
#         invoice_data = sorted(invoice_data, key=lambda i: i.get('gross_profit', 0), reverse=True)

#         if len(invoice_data) > 10:
#             invoice_data = invoice_data[:10]

#         for row in invoice_data:
#             if isinstance(row, dict):
#                 label = row.get('parent_invoice') or row.get('sales_invoice') or row.get('invoice_or_item', '')
#                 if label:
#                     labels.append(label)
#                     datapoints.append(row.get('gross_profit', 0))

#     elif filters.get("group_by"):
#         # For non-invoice groupings
#         grouped_data = [row for row in data if row and row[0]]
#         grouped_data = sorted(grouped_data, key=lambda i: i[-4] if len(i) > 4 else 0, reverse=True)

#         if len(grouped_data) > 10:
#             grouped_data = grouped_data[:10]

#         for row in grouped_data:
#             if row and row[0]:
#                 labels.append(row[0])
#                 if len(row) > 4:
#                     datapoints.append(row[-4])
#                 else:
#                     datapoints.append(0)

#     if not labels or not datapoints:
#         return None

#     return {
#         "data": {
#             "labels": labels,
#             "datasets": [{
#                 "name": _("Gross Profit"),
#                 "values": datapoints
#             }]
#         },
#         "type": "bar",
#         "title": _("Gross Profit by {0}").format(filters.get("group_by", "Invoice")),
#         "fieldtype": "Currency"
#     }

# def get_data_when_grouped_by_invoice(columns, gross_profit_data, filters, group_wise_columns, data):
#     column_names = get_column_names()

#     # to display item as Item Code: Item Name
#     columns[0] = "Sales Invoice:Link/Item:300"

#     for src in gross_profit_data.si_list:
#         row = frappe._dict()
#         row.indent = src.indent
#         row.parent_invoice = src.parent_invoice
#         row["currency"] = src.get("currency")
#         row["company_currency"] = filters.currency

#         for col in group_wise_columns.get(scrub(filters.group_by)):
#             row[column_names[col]] = src.get(col)

#         data.append(row)


# def get_data_when_not_grouped_by_invoice(gross_profit_data, filters, group_wise_columns, data):
#     # Get charges for mapping
#     loading_unloading_charges = get_loading_unloading_charges()
#     foreign_bank_charges_combined = get_foreign_bank_charges_combined()
    
#     for src in gross_profit_data.grouped_data:
#         row = []
#         for col in group_wise_columns.get(scrub(filters.group_by)):
#             row.append(src.get(col))

#         row["currency"] = src.get("currency")
#         row["company_currency"] = filters.currency  
        
#         # Get sales invoice for charge lookups
#         sales_invoice = src.get('parent') or src.get('invoice_or_item')
        
#         # Add loading charges value
#         loading_charge_value = 0.0
#         if sales_invoice and sales_invoice in loading_unloading_charges:
#             loading_charge_value = loading_unloading_charges[sales_invoice]
#         row.append(loading_charge_value)
        
#         # Add combined foreign bank charges value
#         bank_charges_combined_value = 0.0
#         if sales_invoice and sales_invoice in foreign_bank_charges_combined:
#             bank_charges_combined_value = foreign_bank_charges_combined[sales_invoice]
#         row.append(bank_charges_combined_value)

#         data.append(row)


# def get_columns(group_wise_columns, filters, expence_head_columns=None):
#     columns = []
#     column_map = frappe._dict({
#         "parent": {
#             "label": _("Sales Invoice"),
#             "fieldname": "parent_invoice",
#             "fieldtype": "Link",
#             "options": "Sales Invoice",
#             "width": 120,
#         },
#         "invoice_or_item": {
#             "label": _("Sales Invoice"),
#             "fieldtype": "Link",
#             "options": "Sales Invoice",
#             "width": 120,
#         },
#         "posting_date": {
#             "label": _("Posting Date"),
#             "fieldname": "posting_date",
#             "fieldtype": "Date",
#             "width": 100,
#         },
#         "warehouse": {
#             "label": _("Warehouse"),
#             "fieldname": "warehouse",
#             "fieldtype": "Link",
#             "options": "warehouse",
#             "width": 100,
#         },
#         "customer": {
#             "label": _("Customer"),
#             "fieldname": "customer",
#             "fieldtype": "Link",
#             "options": "Customer",
#             "width": 100,
#         },
#         "description": {
#             "label": _("Description"),
#             "fieldname": "description",
#             "fieldtype": "Data",
#             "width": 100,
#         },
#         "final_destination": {
#             "label": _("Final Destination"),
#             "fieldname": "final_destination",
#             "fieldtype": "Data",
#             "width": 120,
#         },
#         "shipping_terms": {
#             "label": _("Shipping Terms"),
#             "fieldname": "shipping_terms",
#             "fieldtype": "Data",
#             "width": 120,
#         },
#         "customer_group": {
#             "label": _("Customer Group"),
#             "fieldname": "customer_group",
#             "fieldtype": "Link",
#             "options": "Customer Group",
#             "width": 100,
#         },
#         "item_group": {
#             "label": _("Item Group"),
#             "fieldname": "item_group",
#             "fieldtype": "Link",
#             "options": "Item Group",
#             "width": 100,
#         },
#         "qty": {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
#         "currency": {
#             "label": _("Invoice Currency"),
#             "fieldname": "currency",
#             "fieldtype": "Link",
#             "options": "Currency",
#             "width": 120,
#         },
#         "company_currency": {
#             "label": _("Company Currency"),
#             "fieldname": "company_currency",
#             "fieldtype": "Link",
#             "options": "Currency",
#             "width": 120,
#         },
        
        
        
#         "rate": {
#             "label": _("Per KG Rate Foreign Currency"),
#             "fieldname": "rate",
#             "fieldtype": "Currency",
#             "options": "currency",
#             "width": 120,
#         },

#         "total": {
#             "label": _("Selling Amount Foreign Currency"),
#             "fieldname": "total",
#             "fieldtype": "Currency",
#             "options": "currency",
#             "width": 120,
#         },
#         "conversion_rate": {
#             "label": _("Exchange Rate"),
#             "fieldname": "conversion_rate",
#             "fieldtype": "Float",
#             "width": 120,
#         },
#         "base_amount": {
#             "label": _("Selling Amount INR"),
#             "fieldname": "selling_amount",
#             "fieldtype": "Currency",
#             "options": "company_currency",
#             "width": 100,
#         },

#         "base_rate": {
#             "label": _("Per KG Rate INR"),
#             "fieldname": "base_rate",
#             "fieldtype": "Currency",
#             "options": "company_currency",
#             "width": 100,
#         },
        
#         "buying_rate": {
#             "label": _("Valuation Rate"),
#             "fieldname": "valuation_rate",
#             "fieldtype": "Currency",
#             "options": "company_currency",
#             "width": 100,
#         },
#         "buying_amount": {
#             "label": _("Buying Amount"),
#             "fieldname": "buying_amount",
#             "fieldtype": "Currency",
#             "options": "company_currency",
#             "width": 100,
#         },
#         "gross_profit": {
#             "label": _("Gross Profit"),
#             "fieldname": "gross_profit",
#             "fieldtype": "Currency",
#             "options": "company_currency",
#             "width": 100,
#         },
#         "gross_profit_percent": {
#             "label": _("Gross Profit Percent"),
#             "fieldname": "gross_profit_%",
#             "fieldtype": "Percent",
#             "width": 100,
#         },
#         # "project": {
#         #     "label": _("Project"),
#         #     "fieldname": "project",
#         #     "fieldtype": "Link",
#         #     "options": "Project",
#         #     "width": 100,
#         # },
#         "no_of_packages": {
#             "label": _("Packing Material Qty"),
#             "fieldname": "no_of_packages",
#             "fieldtype": "Int",
#             "width": 120,
#         },
#         "packaging_material": {
#             "label": _("Packing Material Type"),
#             "fieldname": "packaging_material",
#             "fieldtype": "Link",
#             "options": "Packaging Material",
#             "width": 120,
#         },
#         "debit_in_account_currency": {
#             "label": _("Loading Unloading Charges"),
#             "fieldname": "debit_in_account_currency",
#             "fieldtype": "Currency",
#             "options": "currency",
#             "width": 120,
#         },
#         "foreign_bank_charges_combined": {
#             "label": _("Foreign Bank Charges INR"),
#             "fieldname": "foreign_bank_charges_combined",
#             "fieldtype": "Currency",
#             "options": "company_currency",
#             "width": 180,
#         },
#         "indirect_expence": {
#             "label": _("Indirect Expense"),
#             "fieldname": "indirect_expence",
#             "fieldtype": "Currency",
#             "options": "company_currency",
#             "width": 120,
#         },
#         "per_kg_indirect_expense": {
#             "label": _("Per Kg Indirect Expense"),
#             "fieldname": "per_kg_indirect_expense",
#             "fieldtype": "Currency",
#             "options": "currency",
#             "width": 120,
#         },
#         "buying_plus_indirect": {
#             "label": _("Buying Amount + Indirect Expense"),
#             "fieldname": "buying_plus_indirect",
#             "fieldtype": "Currency",
#             "options": "currency",
#             "width": 120,
#         },
#         "per_kg_cost": {
#             "label": _("Per Kg Cost"),
#             "fieldname": "per_kg_cost",
#             "fieldtype": "Currency",
#             "options": "company_currency",
#             "width": 120,
#         },
#         # "remarks1": {
#         #     "label": _("Remarks1"),
#         #     "fieldname": "remarks1",
#         #     "fieldtype": "Small Text",
#         #     "width": 120,
#         # },
#         # "remarks2": {
#         #     "label": _("Remarks2"),
#         #     "fieldname": "remarks2",
#         #     "fieldtype": "Small Text",
#         #     "width": 120,
#         # },
#         # "remarks3": {
#         #     "label": _("Remarks3"),
#         #     "fieldname": "remarks3",
#         #     "fieldtype": "Small Text",
#         #     "width": 120,
#         # },
#     })

#     for col in group_wise_columns.get(scrub(filters.group_by)):
#         col_def = column_map.get(col)
#         if col_def:
#             columns.append(col_def)

       
#     if expence_head_columns:
#         columns.extend(expence_head_columns)

#     # Add charge columns for non-Invoice groupings
#     if filters.group_by != "Invoice":
#         columns.extend([
#             {
#                 "label": _("Loading Unloading Charges"),
#                 "fieldname": "loading_unloading_charges",
#                 "fieldtype": "Currency",
#                 "options": "currency",
#                 "width": 120,
#             },
#             {
#                 "label": _("Foreign Bank Charges INR"),
#                 "fieldname": "foreign_bank_charges_combined",
#                 "fieldtype": "Currency",
#                 "options": "currency",
#                 "width": 180,
#             },
#         ])

#     columns.append({
#         "fieldname": "currency",
#         "label": _("Currency"),
#         "fieldtype": "Link",
#         "options": "Currency",
#         "hidden": 1,
#     })

#     columns.append({
# 		"fieldname": "company_currency",
# 		"label": _("Company Currency"),
# 		"fieldtype": "Link",
# 		"options": "Currency",
# 		"hidden": 1,
# 	})

#     columns.extend([
#         # {
#         #     "label": _("Remarks1"),
#         #     "fieldname": "remarks1",
#         #     "fieldtype": "Small Text",
#         #     "width": 120,
#         # },
#         # {
#         #     "label": _("Remarks2"),
#         #     "fieldname": "remarks2",
#         #     "fieldtype": "Small Text",
#         #     "width": 120,
#         # },
#         # {
#         #     "label": _("Remarks3"),
#         #     "fieldname": "remarks3",
#         #     "fieldtype": "Small Text",
#         #     "width": 120,
#         # },
#     ])

#     # ---- Append Remarks at the END ----

#     return columns


# def get_column_names():
#     return frappe._dict({
#         "invoice_or_item": "sales_invoice",
#         "posting_date": "posting_date",
#         "warehouse": "warehouse",
#         "customer": "customer",
#         "description": "description",
#         "final_destination": "final_destination",
#         "shipping_terms": "shipping_terms",
#         "customer_group": "customer_group",
#         "item_group": "item_group",
#         "qty": "qty",
#         "currency": "currency",
#         "company_currency": "company_currency",
#         "rate": "rate",
#         "total": "total",
#         "conversion_rate": "conversion_rate",
#         "base_amount": "selling_amount",
#         "base_rate": "base_rate",
#         "buying_rate": "valuation_rate",
#         "buying_amount": "buying_amount",
#         "gross_profit": "gross_profit",
#         "gross_profit_percent": "gross_profit_%",
#         "project": "project",
#         "no_of_packages": "no_of_packages",
#         "packaging_material": "packaging_material",
#         "debit_in_account_currency": "debit_in_account_currency",
#         "foreign_bank_charges_combined": "foreign_bank_charges_combined",
#         "indirect_expence": "indirect_expence",
#         "per_kg_indirect_expense": "per_kg_indirect_expense",
#         "buying_plus_indirect": "buying_plus_indirect",
#         "per_kg_cost": "per_kg_cost",
#         # "remarks1": "remarks1",
#         # "remarks2": "remarks2",
#         # "remarks3": "remarks3",
#     })


# class GrossProfitGenerator(object):
#     def __init__(self, filters=None):
#         self.data = []
#         self.average_buying_rate = {}
#         self.filters = frappe._dict(filters)
#         self.load_invoice_items()

#         if filters.group_by == "Invoice":
#             self.group_items_by_invoice()

#         self.load_stock_ledger_entries()
#         self.load_product_bundle()
#         self.load_non_stock_items()
#         self.get_returned_invoice_items()
#         self.process()
#         self.final_data()

#     def load_invoice_items(self):
#         conditions = ""
#         if self.filters.company:
#             conditions += " and company = %(company)s"
#         if self.filters.from_date:
#             conditions += " and posting_date >= %(from_date)s"
#         if self.filters.to_date:
#             conditions += " and posting_date <= %(to_date)s"

#         if self.filters.group_by == "Sales Person":
#             sales_person_cols = ", sales.sales_person, sales.allocated_amount, sales.incentives"
#             sales_team_table = "left join `tabSales Team` sales on sales.parent = `tabSales Invoice`.name"
#         else:
#             sales_person_cols = ""
#             sales_team_table = ""

#         if self.filters.get("sales_invoice"):
#             conditions += " and `tabSales Invoice`.name = %(sales_invoice)s"
#         if self.filters.get("item_code"):
#             conditions += " and `tabSales Invoice Item`.item_code = %(item_code)s"

#         self.si_list = frappe.db.sql("""
#             select
#                 `tabSales Invoice Item`.parenttype,
#                 `tabSales Invoice Item`.parent,
#                 `tabSales Invoice`.posting_date,
#                 `tabSales Invoice`.shipping_terms,
#                 `tabSales Invoice`.posting_time,
#                 `tabSales Invoice`.project,
#                 `tabSales Invoice`.update_stock,
#                 `tabSales Invoice`.customer,
#                 `tabSales Invoice`.customer_group,
#                 `tabSales Invoice`.territory,
#                 `tabSales Invoice Item`.item_code,
#                 `tabSales Invoice Item`.item_name,
#                 `tabSales Invoice Item`.description,
#                 `tabSales Invoice Item`.warehouse,
#                 `tabSales Invoice Item`.item_group,
#                 `tabSales Invoice Item`.brand,
#                 `tabSales Invoice Item`.dn_detail,
#                 `tabSales Invoice Item`.delivery_note,
#                 `tabSales Invoice Item`.stock_qty as qty,
#                 `tabSales Invoice Item`.base_net_rate,
#                 `tabSales Invoice Item`.base_net_amount,
#                 `tabSales Invoice Item`.name as "item_row",
#                 `tabSales Invoice`.is_return,
#                 `tabSales Invoice`.final_destination,
#                 `tabSales Invoice Item`.cost_center,
#                 `tabSales Invoice`.conversion_rate,
#                 `tabSales Invoice`.currency,
#                 `tabSales Invoice`.total,
#                 `tabSales Invoice Item`.rate,
#                 `tabSales Invoice Item`.no_of_packages,
#                 `tabSales Invoice Item`.packaging_material
#             from
#                 `tabSales Invoice`
#             inner join
#                 `tabSales Invoice Item` on `tabSales Invoice Item`.parent = `tabSales Invoice`.name
#             {sales_team_table}
#             where
#                 `tabSales Invoice`.docstatus = 1
#                 and `tabSales Invoice`.is_opening != 'Yes'
#                 {conditions}
#                 {match_cond}
#             order by
#                 `tabSales Invoice`.posting_date desc,
#                 `tabSales Invoice`.posting_time desc
#         """.format(
#             conditions=conditions,
#             sales_team_table=sales_team_table,
#             match_cond=get_match_cond("Sales Invoice"),
#         ), self.filters, as_dict=1)

#     def final_data(self):
#         indirect_expence_dict = {}

#         indirect_expence_data = frappe.db.sql("""
#             SELECT
#                 si.name as sales_invoice, sum(pi.base_total) as net_total
#             FROM
#                 `tabPurchase Invoice` as pi
#                 LEFT JOIN `tabSales Invoice` as si on pi.sales_invoice = si.name and si.docstatus = 1
#             WHERE
#                 pi.docstatus = 1 and pi.sales_invoice is not null and pi.sales_invoice != ''
#             group by si.name
#         """, as_dict=1)

#         for row in indirect_expence_data:
#             indirect_expence_dict[row.sales_invoice] = row.net_total

#         si_amount_dict = {}
        
#         for row in self.si_list:
#             if (row.indent == 0 and indirect_expence_dict.get(row.invoice_or_item)):
#                 si_amount_dict[row.invoice_or_item] = {
#                     'total_base_amount': (row.base_amount - row.buying_amount), 
#                     'total_indirect_expence': indirect_expence_dict.get(row.invoice_or_item)
#                 }
#             elif indirect_expence_dict.get(row.parent) and self.filters.get("group_by") != "Invoice":
#                 si_amount_dict[row.parent] = {
#                     'total_base_amount': (row.base_amount - row.buying_amount), 
#                     'total_indirect_expence': indirect_expence_dict.get(row.parent, 0)
#                 }

#         invoice_list = []

#         for row in self.si_list[::-1]:
#             if si_amount_dict.get(row.invoice_or_item):
#                 row.indirect_expence = (si_amount_dict[row.invoice_or_item]["total_indirect_expence"] * (row.base_amount - row.buying_amount)) / si_amount_dict[row.invoice_or_item]["total_base_amount"]
#                 row.gross_profit = row.gross_profit - row.indirect_expence
#                 if row.base_amount:
#                     row.gross_profit_percent = flt((row.gross_profit / row.base_amount) * 100.0, 2)
#                 else:
#                     row.gross_profit_percent = 0.0
    
#             elif si_amount_dict.get(row.parent_invoice):
#                 row.indirect_expence = (si_amount_dict[row.parent_invoice]["total_indirect_expence"] * (row.base_amount - row.buying_amount)) / si_amount_dict[row.parent_invoice]["total_base_amount"]
#                 row.gross_profit = row.gross_profit - (si_amount_dict[row.parent_invoice]["total_indirect_expence"] * (row.base_amount - row.buying_amount)) / si_amount_dict[row.parent_invoice]["total_base_amount"]
#                 if row.base_amount:
#                     row.gross_profit_percent = flt((row.gross_profit / row.base_amount) * 100.0, 2)
#                 else:
#                     row.gross_profit_percent = 0.0

#             elif self.filters.get("group_by") != "Invoice" and si_amount_dict.get(row.parent):
#                 if row.item_code not in invoice_list:
#                     if row.get('base_amount') or row.get('buying_amount'):
#                         row.gross_profit = row.gross_profit - (si_amount_dict[row.parent]['total_indirect_expence'] * (row.get('base_amount') - row.get('buying_amount')) / (row.get('base_amount') - row.get('buying_amount')))
#                     else:
#                         row.gross_profit = row.gross_profit
#                     if row.base_amount:
#                         row.gross_profit_percent = flt((row.gross_profit / row.base_amount) * 100.0, 2)
#                     else:
#                         row.gross_profit_percent = 0.0
#                     invoice_list.append(row.item_code)
#             else:
#                 row.indirect_expence = 0

#     def process(self):
#         self.grouped = {}
#         self.grouped_data = []

#         self.currency_precision = cint(frappe.db.get_default("currency_precision")) or 3
#         self.float_precision = cint(frappe.db.get_default("float_precision")) or 2

#         grouped_by_invoice = True if self.filters.get("group_by") == "Invoice" else False

#         if grouped_by_invoice:
#             buying_amount = 0

#         for row in reversed(self.si_list):
#             if self.skip_row(row):
#                 continue

#             row.base_amount = flt(row.base_net_amount, self.currency_precision)
#             row.currency = row.currency
#             row.company_currency = self.filters.currency

#             product_bundles = []
#             if row.update_stock:
#                 product_bundles = self.product_bundles.get(row.parenttype, {}).get(row.parent, frappe._dict())
#             elif row.dn_detail:
#                 product_bundles = self.product_bundles.get("Delivery Note", {}).get(row.delivery_note, frappe._dict())
#                 row.item_row = row.dn_detail

#             # get buying amount
#             if row.item_code in product_bundles:
#                 row.buying_amount = flt(self.get_buying_amount_from_product_bundle(row, product_bundles[row.item_code]), self.currency_precision)
#             else:
#                 row.buying_amount = flt(self.get_buying_amount(row, row.item_code), self.currency_precision)

#             if grouped_by_invoice:
#                 if row.indent == 1.0:
#                     buying_amount += row.buying_amount
#                 elif row.indent == 0.0:
#                     row.buying_amount = buying_amount
#                     buying_amount = 0

#             # get buying rate
#             if flt(row.qty):
#                 row.buying_rate = flt(row.buying_amount / flt(row.qty), self.float_precision)
#                 row.base_rate = flt(row.base_amount / flt(row.qty), self.float_precision)
#             else:
#                 if self.is_not_invoice_row(row):
#                     row.buying_rate, row.base_rate = 0.0, 0.0

#             # calculate gross profit
#             row.gross_profit = flt(row.base_amount - row.buying_amount, self.currency_precision)
#             if row.base_amount:
#                 row.gross_profit_percent = flt((row.gross_profit / row.base_amount) * 100.0, self.currency_precision)
#             else:
#                 row.gross_profit_percent = 0.0

#             # add to grouped
#             self.grouped.setdefault(row.get(scrub(self.filters.group_by)), []).append(row)

#         if self.grouped:
#             self.get_average_rate_based_on_group_by()

#     def get_average_rate_based_on_group_by(self):
#         for key in list(self.grouped):
#             if self.filters.get("group_by") != "Invoice":
#                 for i, row in enumerate(self.grouped[key]):
#                     if i == 0:
#                         new_row = row
#                     else:
#                         new_row.qty += flt(row.qty)
#                         new_row.buying_amount += flt(row.buying_amount, self.currency_precision)
#                         new_row.base_amount += flt(row.base_amount, self.currency_precision)
#                 new_row = self.set_average_rate(new_row)
#                 self.grouped_data.append(new_row)
#             else:
#                 for i, row in enumerate(self.grouped[key]):
#                     if row.indent == 1.0:
#                         if (row.parent in self.returned_invoices and row.item_code in self.returned_invoices[row.parent]):
#                             returned_item_rows = self.returned_invoices[row.parent][row.item_code]
#                             for returned_item_row in returned_item_rows:
#                                 row.qty += flt(returned_item_row.qty)
#                                 row.base_amount += flt(returned_item_row.base_amount, self.currency_precision)
#                             row.buying_amount = flt(flt(row.qty) * flt(row.buying_rate), self.currency_precision)
#                         if flt(row.qty) or row.base_amount:
#                             row = self.set_average_rate(row)
#                             self.grouped_data.append(row)

#     def is_not_invoice_row(self, row):
#         return (self.filters.get("group_by") == "Invoice" and row.indent != 0.0) or self.filters.get("group_by") != "Invoice"

#     def set_average_rate(self, new_row):
#         self.set_average_gross_profit(new_row)
#         new_row.buying_rate = flt(new_row.buying_amount / new_row.qty, self.float_precision) if new_row.qty else 0
#         new_row.base_rate = flt(new_row.base_amount / new_row.qty, self.float_precision) if new_row.qty else 0
#         return new_row

#     def set_average_gross_profit(self, new_row):
#         new_row.gross_profit = flt(new_row.base_amount - new_row.buying_amount, self.currency_precision)
#         new_row.gross_profit_percent = flt(((new_row.gross_profit / new_row.base_amount) * 100.0), self.currency_precision) if new_row.base_amount else 0
#         new_row.buying_rate = flt(new_row.buying_amount / flt(new_row.qty), self.float_precision) if flt(new_row.qty) else 0
#         new_row.base_rate = flt(new_row.base_amount / flt(new_row.qty), self.float_precision) if flt(new_row.qty) else 0

#     def get_returned_invoice_items(self):
#         returned_invoices = frappe.db.sql("""
#             select
#                 si.name, si_item.item_code, si_item.stock_qty as qty, si_item.base_net_amount as base_amount, si.return_against
#             from
#                 `tabSales Invoice` si, `tabSales Invoice Item` si_item
#             where
#                 si.name = si_item.parent
#                 and si.docstatus = 1
#                 and si.is_return = 1
#         """, as_dict=1)

#         self.returned_invoices = frappe._dict()
#         for inv in returned_invoices:
#             self.returned_invoices.setdefault(inv.return_against, frappe._dict()).setdefault(inv.item_code, []).append(inv)

#     def skip_row(self, row):
#         if self.filters.get("group_by") != "Invoice":
#             if not row.get(scrub(self.filters.get("group_by", ""))):
#                 return True
#         return False

#     def get_buying_amount_from_product_bundle(self, row, product_bundle):
#         buying_amount = 0.0
#         for packed_item in product_bundle:
#             if packed_item.get("parent_detail_docname") == row.item_row:
#                 buying_amount += self.get_buying_amount(row, packed_item.item_code)
#         return flt(buying_amount, self.currency_precision)

#     def get_buying_amount(self, row, item_code):
#         if item_code in self.non_stock_items and (row.project or row.cost_center):
#             item_rate = self.get_last_purchase_rate(item_code, row)
#             return flt(row.qty) * item_rate
#         else:
#             my_sle = self.sle.get((item_code, row.warehouse))
#             if (row.update_stock or row.dn_detail) and my_sle:
#                 parenttype, parent = row.parenttype, row.parent
#                 if row.dn_detail:
#                     parenttype, parent = "Delivery Note", row.delivery_note

#                 for i, sle in enumerate(my_sle):
#                     if (sle.voucher_type == parenttype and parent == sle.voucher_no and sle.voucher_detail_no == row.item_row):
#                         previous_stock_value = len(my_sle) > i + 1 and flt(my_sle[i + 1].stock_value) or 0.0
#                         if previous_stock_value:
#                             return (previous_stock_value - flt(sle.stock_value)) * flt(row.qty) / abs(flt(sle.qty))
#                         else:
#                             return flt(row.qty) * self.get_average_buying_rate(row, item_code)
#             else:
#                 return flt(row.qty) * self.get_average_buying_rate(row, item_code)
#         return 0.0

#     def get_average_buying_rate(self, row, item_code):
#         args = row
#         if not item_code in self.average_buying_rate:
#             args.update({
#                 "voucher_type": row.parenttype,
#                 "voucher_no": row.parent,
#                 "allow_zero_valuation": True,
#                 "company": self.filters.company,
#                 "qty": row.qty,
#                 "serial_no": None,
#                 "batch_no": None,
#                 "posting_date": row.posting_date,
#                 "posting_time": row.posting_time if hasattr(row, 'posting_time') else None
#             })
#             try:
#                 average_buying_rate = get_incoming_rate(args)
#                 self.average_buying_rate[item_code] = flt(average_buying_rate) if average_buying_rate else 0.0
#             except Exception as e:
#                 frappe.log_error(f"Error in get_average_buying_rate for item {item_code}: {str(e)}")
#                 self.average_buying_rate[item_code] = 0.0
#         return self.average_buying_rate.get(item_code, 0.0)

#     def get_last_purchase_rate(self, item_code, row):
#         try:
#             purchase_invoice = frappe.qb.DocType("Purchase Invoice")
#             purchase_invoice_item = frappe.qb.DocType("Purchase Invoice Item")

#             query = (
#                 frappe.qb.from_(purchase_invoice_item)
#                 .inner_join(purchase_invoice)
#                 .on(purchase_invoice.name == purchase_invoice_item.parent)
#                 .select(purchase_invoice_item.base_rate / purchase_invoice_item.conversion_factor)
#                 .where(purchase_invoice.docstatus == 1)
#                 .where(purchase_invoice.posting_date <= self.filters.to_date)
#                 .where(purchase_invoice_item.item_code == item_code)
#             )

#             if row.project:
#                 query.where(purchase_invoice_item.project == row.project)
#             if row.cost_center:
#                 query.where(purchase_invoice_item.cost_center == row.cost_center)

#             query.orderby(purchase_invoice.posting_date, order=frappe.qb.desc)
#             query.limit(1)
#             last_purchase_rate = query.run()

#             return flt(last_purchase_rate[0][0]) if last_purchase_rate and last_purchase_rate[0][0] else 0
#         except Exception as e:
#             frappe.log_error(f"Error in get_last_purchase_rate for item {item_code}: {str(e)}")
#             return 0

#     def group_items_by_invoice(self):
#         parents = []
#         for row in self.si_list:
#             if row.parent not in parents:
#                 parents.append(row.parent)

#         parents_index = 0
#         for index, row in enumerate(self.si_list):
#             if parents_index < len(parents) and row.parent == parents[parents_index]:
#                 invoice = self.get_invoice_row(row)
#                 self.si_list.insert(index, invoice)
#                 parents_index += 1
#             else:
#                 if not row.indent:
#                     row.indent = 1.0
#                     row.parent_invoice = row.parent
#                     row.invoice_or_item = row.item_code
#                     if frappe.db.exists("Product Bundle", row.item_code):
#                         self.add_bundle_items(row, index)

#     def get_invoice_row(self, row):
#         return frappe._dict({
#             "parent_invoice": "",
#             "indent": 0.0,
#             "invoice_or_item": row.parent,
#             "parent": None,
#             "posting_date": row.posting_date,
#             "posting_time": row.posting_time,
#             "project": row.project,
#             "update_stock": row.update_stock,
#             "customer": row.customer,
#             "customer_group": row.customer_group,
#             "item_code": None,
#             "item_name": None,
#             "description": row.description,
#             "warehouse": None,
#             "item_group": None,
#             "brand": None,
#             "dn_detail": None,
#             "delivery_note": None,
#             "qty": None,
#             "item_row": None,
#             "is_return": row.is_return,
#             "cost_center": row.cost_center,
#             "final_destination": row.final_destination,
#             "shipping_terms": row.shipping_terms,
#             "conversion_rate": row.conversion_rate,
#             "currency": row.currency,
#             "total": row.total,
#             "rate": row.rate,
#             "no_of_packages": row.no_of_packages,
#             "packaging_material": row.packaging_material,
           
#             "base_net_amount": frappe.db.get_value("Sales Invoice", row.parent, "base_net_total") or 0,
#         })

#     def add_bundle_items(self, product_bundle, index):
#         bundle_items = self.get_bundle_items(product_bundle)
#         for i, item in enumerate(bundle_items):
#             bundle_item = self.get_bundle_item_row(product_bundle, item)
#             self.si_list.insert((index + i + 1), bundle_item)

#     def get_bundle_items(self, product_bundle):
#         return frappe.get_all("Product Bundle Item", filters={"parent": product_bundle.item_code}, fields=["item_code", "qty"])

#     def get_bundle_item_row(self, product_bundle, item):
#         item_name, description, item_group, brand = self.get_bundle_item_details(item.item_code)
#         return frappe._dict({
#             "parent_invoice": product_bundle.item_code,
#             "indent": product_bundle.indent + 1,
#             "parent": None,
#             "invoice_or_item": item.item_code,
#             "posting_date": product_bundle.posting_date,
#             "posting_time": product_bundle.posting_time,
#             "project": product_bundle.project,
#             "customer": product_bundle.customer,
#             "customer_group": product_bundle.customer_group,
#             "item_code": item.item_code,
#             "item_name": item_name,
#             "description": description,
#             "warehouse": product_bundle.warehouse,
#             "item_group": item_group,
#             "brand": brand,
#             "dn_detail": product_bundle.dn_detail,
#             "delivery_note": product_bundle.delivery_note,
#             "qty": (flt(product_bundle.qty) * flt(item.qty)),
#             "item_row": None,
#             "is_return": product_bundle.is_return,
#             "cost_center": product_bundle.cost_center,
#         })

#     def get_bundle_item_details(self, item_code):
#         return frappe.db.get_value("Item", item_code, ["item_name", "description", "item_group", "brand"])

#     def load_stock_ledger_entries(self):
#         res = frappe.db.sql("""
#             select item_code, voucher_type, voucher_no, voucher_detail_no, stock_value, warehouse, actual_qty as qty
#             from `tabStock Ledger Entry`
#             where company=%(company)s and is_cancelled = 0
#             order by item_code desc, warehouse desc, posting_date desc, posting_time desc, creation desc
#         """, self.filters, as_dict=True)
        
#         self.sle = {}
#         for r in res:
#             if (r.item_code, r.warehouse) not in self.sle:
#                 self.sle[(r.item_code, r.warehouse)] = []
#             self.sle[(r.item_code, r.warehouse)].append(r)

#     def load_product_bundle(self):
#         self.product_bundles = {}
#         for d in frappe.db.sql("""
#             select parenttype, parent, parent_item, item_code, warehouse, -1*qty as total_qty, parent_detail_docname
#             from `tabPacked Item` where docstatus=1
#         """, as_dict=True):
#             self.product_bundles.setdefault(d.parenttype, frappe._dict()).setdefault(d.parent, frappe._dict()).setdefault(d.parent_item, []).append(d)

#     def load_non_stock_items(self):
#         self.non_stock_items = frappe.db.sql_list("select name from tabItem where is_stock_item=0")



from collections import defaultdict
import frappe
from frappe import _, scrub
from frappe.utils import cint, flt
from erpnext.controllers.queries import get_match_cond
from erpnext.stock.utils import get_incoming_rate


def execute(filters=None):
    if not filters:
        filters = frappe._dict()
    filters.currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    
    gross_profit_data = GrossProfitGenerator(filters)
    data = []
    
    # --- Purchase Invoice based indirect expenses ---
    indirect_expence_data_account_wise = frappe.db.sql("""
        SELECT
            pii.indirect_expense_for_sales AS sales_invoice,
            pii.expense_account,
            SUM(pii.base_amount) AS expense_amount
        FROM
            `tabPurchase Invoice Item` AS pii
        INNER JOIN `tabPurchase Invoice` AS pi ON pii.parent = pi.name AND pi.docstatus = 1
        INNER JOIN `tabSales Invoice` AS si ON pii.indirect_expense_for_sales = si.name AND si.docstatus = 1
        WHERE
            pii.indirect_expense_for_sales IS NOT NULL
            AND pii.indirect_expense_for_sales != ''
        GROUP BY
            pii.indirect_expense_for_sales,
            pii.expense_account
    """, as_dict=1)
    
    sales_invoice_expenses = defaultdict(list)
    expence_accounts = set()
    for row in indirect_expence_data_account_wise:
        company = frappe.get_value("Account", row["expense_account"], "company")
        if company == filters.company:
            expence_accounts.add(row["expense_account"])
    expence_accounts = sorted(list(expence_accounts))
    expence_head_columns = [
        {"label": account, "fieldname": scrub(account), "fieldtype": "Currency", "options": "company_currency", "width": 120}
        for account in expence_accounts
    ]

    for row in indirect_expence_data_account_wise:
        sales_invoice_expenses[row["sales_invoice"]].append({
            "expense_account": row["expense_account"],
            "expense_amount": row["expense_amount"]
        })
    
    # --- Journal Entry based charges ---
    loading_unloading_charges = get_loading_unloading_charges()
    insurance_charges = get_insurance_charges()
    foreign_bank_charges = get_foreign_bank_charges()
    
    # --- Columns setup ---
    group_wise_columns = frappe._dict({
        "invoice": [
            "invoice_or_item", "posting_date", "warehouse", "customer", "description", "final_destination", "shipping_terms", 
            "customer_group", "item_group", "qty", "currency", "company_currency", "rate", "total", "conversion_rate", 
            "base_amount", "base_rate", "buying_rate", "buying_amount", "gross_profit", "gross_profit_percent",
            "no_of_packages", "packaging_material", "debit_in_account_currency", "insurance_charges",
            "foreign_bank_charges", "indirect_expence", "per_kg_indirect_expense", "buying_plus_indirect",
            "per_kg_cost"
        ],
    })
    
    columns = get_columns(group_wise_columns, filters, expence_head_columns)
    
    # --- Data fetch ---
    if filters.group_by == "Invoice":
        get_data_when_grouped_by_invoice(columns, gross_profit_data, filters, group_wise_columns, data)
    else:
        get_data_when_not_grouped_by_invoice(gross_profit_data, filters, group_wise_columns, data)
    
    chart_data = get_chart_data(data, filters)
    
    # --- Process data rows ---
    # Accounts that are in foreign currency and need conversion
    foreign_currency_accounts = {scrub("Freight Outward - UCPL")}

    for row in data:
        sales_invoice_name = None
        
        if isinstance(row, dict):
            sales_invoice_name = row.get('sales_invoice') or row.get('invoice_or_item') or row.get('parent_invoice')
        
        if sales_invoice_name:
            expence_accounts_for_invoice = sales_invoice_expenses.get(sales_invoice_name, [])
            for expense in expence_accounts_for_invoice:
                if isinstance(row, dict):
                    row[scrub(expense["expense_account"])] = expense["expense_amount"]
        
        if isinstance(row, dict):
            # Set Loading Unloading Charges (always in INR/company currency)
            row['debit_in_account_currency'] = loading_unloading_charges.get(sales_invoice_name, 0.0)
            
            # Set Insurance Charges (Marine Insurance)
            row['insurance_charges'] = insurance_charges.get(sales_invoice_name, 0.0)
            
            # Set Foreign Bank Charges (always in INR/company currency)
            row['foreign_bank_charges'] = foreign_bank_charges.get(sales_invoice_name, 0.0)
            
            # SIMPLE CALCULATION: Sum only the three main columns shown in your image
            total_indirect_expence = (
                flt(row.get('debit_in_account_currency', 0.0)) +  # Loading Unloading Charges
                flt(row.get('insurance_charges', 0.0)) +          # Insurance (Marine) - UCPL
                flt(row.get('foreign_bank_charges', 0.0)) +       # Foreign Bank Charges INR
                flt(row.get(scrub("Export Bank Charges - UCPL"), 0.0)) +  # Export Bank Charges
                flt(row.get(scrub("Export Expense - UCPL"), 0.0)) +       # Export Expense
                flt(row.get(scrub("Freight Outward - UCPL"), 0.0)) +      # Freight Outward
                flt(row.get(scrub("Packing Expense - UCPL"), 0.0)) +      # Packing Expense
                flt(row.get(scrub("Selling Commission - UCPL"), 0.0))  # Selling Commission
            )

            # Store the total in indirect_expence column
            row["indirect_expence"] = total_indirect_expence
            
            # Calculate Per Kg Indirect Expense (INR per KG)
            if flt(row.get("qty", 0)):
                row["per_kg_indirect_expense"] = flt(total_indirect_expence / flt(row["qty"]), 2)
            else:
                row["per_kg_indirect_expense"] = 0.0
            
            # Calculate Buying Amount + Indirect Expense
            row["buying_plus_indirect"] = flt(row.get("buying_amount", 0)) + total_indirect_expence
            
            # Calculate Per Kg Cost (INR per KG)
            if flt(row.get("qty", 0)):
                row["per_kg_cost"] = flt(row["buying_plus_indirect"] / flt(row["qty"]), 2)
            else:
                row["per_kg_cost"] = 0.0

    return columns, data, None, chart_data


def get_loading_unloading_charges():
    """
    Get Loading Unloading Charges from Journal Entry
    Exclude Insurance charges
    """
    loading_charges_data = frappe.db.sql("""
        SELECT 
            jea.sales_invoice as sales_invoice,
            SUM(jea.debit) as loading_charges
        FROM 
            `tabJournal Entry` je
        INNER JOIN 
            `tabJournal Entry Account` jea ON je.name = jea.parent
        INNER JOIN 
            `tabAccount` acc ON jea.account = acc.name
        WHERE 
            je.docstatus = 1
            AND jea.sales_invoice IS NOT NULL
            AND jea.sales_invoice != ''
            AND acc.root_type = 'Expense'
            AND (acc.account_name IN ('Loading', 'Unloading', 'Loading & Unloading')
                 OR acc.name LIKE '%Loading%' OR acc.name LIKE '%Unloading%')
            AND acc.name NOT LIKE '%Insurance%'
            AND jea.debit > 0
        GROUP BY 
            jea.sales_invoice
    """, as_dict=1)
    
    loading_charges_dict = {}
    for row in loading_charges_data:
        if row.sales_invoice:
            loading_charges_dict[row.sales_invoice] = row.loading_charges
    
    return loading_charges_dict


def get_insurance_charges():
    """
    Get Insurance (Marine) - UCPL charges from Journal Entry
    """
    insurance_data = frappe.db.sql("""
        SELECT 
            jea.sales_invoice as sales_invoice,
            SUM(jea.debit) as insurance_amount
        FROM 
            `tabJournal Entry` je
        INNER JOIN 
            `tabJournal Entry Account` jea ON je.name = jea.parent
        INNER JOIN 
            `tabAccount` acc ON jea.account = acc.name
        WHERE 
            je.docstatus = 1
            AND jea.sales_invoice IS NOT NULL
            AND jea.sales_invoice != ''
            AND (acc.account_name LIKE '%Insurance%' OR acc.name LIKE '%Insurance%')
            AND jea.debit > 0
        GROUP BY 
            jea.sales_invoice
    """, as_dict=1)
    
    insurance_dict = {}
    for row in insurance_data:
        if row.sales_invoice:
            insurance_dict[row.sales_invoice] = row.insurance_amount
    
    return insurance_dict


def get_foreign_bank_charges():
    """
    Get Foreign Bank Charges - always in INR/company currency
    Renamed from "Foreign Bank Charges Foreign Currency & INR" to "Foreign Bank Charges INR"
    """
    bank_charges_data = frappe.db.sql("""
        SELECT 
            jea.sales_invoice as sales_invoice,
            SUM(jea.debit) as bank_charges
        FROM 
            `tabJournal Entry` je
        INNER JOIN 
            `tabJournal Entry Account` jea ON je.name = jea.parent
        INNER JOIN 
            `tabAccount` acc ON jea.account = acc.name
        WHERE 
            je.docstatus = 1
            AND jea.sales_invoice IS NOT NULL
            AND jea.sales_invoice != ''
            AND (acc.account_name IN ('Foreign Bank Charges', 'Bank Charges')
                 OR acc.name LIKE '%Foreign Bank%' OR acc.name LIKE '%Bank Charge%')
            AND jea.debit > 0
        GROUP BY 
            jea.sales_invoice
    """, as_dict=1)
    
    bank_charges_dict = {}
    for row in bank_charges_data:
        if row.sales_invoice:
            bank_charges_dict[row.sales_invoice] = row.bank_charges
    
    return bank_charges_dict


def get_chart_data(data, filters):
    if not data:
        return None
    
    labels = []
    datapoints = []

    if filters.get("group_by") == "Invoice":
        invoice_data = [row for row in data if isinstance(row, dict) and row.get('indent', 1) == 0]
        invoice_data = sorted(invoice_data, key=lambda i: i.get('gross_profit', 0), reverse=True)

        if len(invoice_data) > 10:
            invoice_data = invoice_data[:10]

        for row in invoice_data:
            if isinstance(row, dict):
                label = row.get('parent_invoice') or row.get('sales_invoice') or row.get('invoice_or_item', '')
                if label:
                    labels.append(label)
                    datapoints.append(row.get('gross_profit', 0))

    elif filters.get("group_by"):
        grouped_data = [row for row in data if row and row[0]]
        grouped_data = sorted(grouped_data, key=lambda i: i[-4] if len(i) > 4 else 0, reverse=True)

        if len(grouped_data) > 10:
            grouped_data = grouped_data[:10]

        for row in grouped_data:
            if row and row[0]:
                labels.append(row[0])
                if len(row) > 4:
                    datapoints.append(row[-4])
                else:
                    datapoints.append(0)

    if not labels or not datapoints:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [{
                "name": _("Gross Profit"),
                "values": datapoints
            }]
        },
        "type": "bar",
        "title": _("Gross Profit by {0}").format(filters.get("group_by", "Invoice")),
        "fieldtype": "Currency"
    }


def get_data_when_grouped_by_invoice(columns, gross_profit_data, filters, group_wise_columns, data):
    column_names = get_column_names()

    columns[0] = "Sales Invoice:Link/Item:300"

    for src in gross_profit_data.si_list:
        row = frappe._dict()
        row.indent = src.indent
        row.parent_invoice = src.parent_invoice
        row["currency"] = src.get("currency")
        row["company_currency"] = filters.currency

        for col in group_wise_columns.get(scrub(filters.group_by)):
            if col in column_names:
                row[column_names[col]] = src.get(col)

        data.append(row)


def get_data_when_not_grouped_by_invoice(gross_profit_data, filters, group_wise_columns, data):
    # Get charges for mapping
    loading_unloading_charges = get_loading_unloading_charges()
    insurance_charges = get_insurance_charges()
    foreign_bank_charges = get_foreign_bank_charges()
    
    for src in gross_profit_data.grouped_data:
        row = frappe._dict()
        for col in group_wise_columns.get(scrub(filters.group_by)):
            row[col] = src.get(col)

        row["currency"] = src.get("currency", filters.currency)
        row["company_currency"] = filters.currency
        
        # Get sales invoice for charge lookups
        sales_invoice = src.get('parent') or src.get('invoice_or_item')
        
        # Add loading charges value
        row["debit_in_account_currency"] = loading_unloading_charges.get(sales_invoice, 0.0)
        
        # Add insurance charges value
        row["insurance_charges"] = insurance_charges.get(sales_invoice, 0.0)
        
        # Add foreign bank charges value
        row["foreign_bank_charges"] = foreign_bank_charges.get(sales_invoice, 0.0)

        data.append(row)


def get_columns(group_wise_columns, filters, expence_head_columns=None):
    columns = []
    column_map = frappe._dict({
        "parent": {
            "label": _("Sales Invoice"),
            "fieldname": "parent_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 120,
        },
        "invoice_or_item": {
            "label": _("Sales Invoice"),
            "fieldname": "sales_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 120,
        },
        "posting_date": {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100,
        },
        "warehouse": {
            "label": _("Warehouse"),
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 100,
        },
        "customer": {
            "label": _("Customer"),
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 100,
        },
        "description": {
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "Data",
            "width": 100,
        },
        "final_destination": {
            "label": _("Final Destination"),
            "fieldname": "final_destination",
            "fieldtype": "Data",
            "width": 120,
        },
        "shipping_terms": {
            "label": _("Shipping Terms"),
            "fieldname": "shipping_terms",
            "fieldtype": "Data",
            "width": 120,
        },
        "customer_group": {
            "label": _("Customer Group"),
            "fieldname": "customer_group",
            "fieldtype": "Link",
            "options": "Customer Group",
            "width": 100,
        },
        "item_group": {
            "label": _("Item Group"),
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 100,
        },
        "qty": {
            "label": _("Qty"), 
            "fieldname": "qty", 
            "fieldtype": "Float", 
            "width": 80
        },
        "currency": {
            "label": _("Invoice Currency"),
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 120,
        },
        "company_currency": {
            "label": _("Company Currency"),
            "fieldname": "company_currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 120,
        },
        "rate": {
            "label": _("Per KG Rate Foreign Currency"),
            "fieldname": "rate",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        "total": {
            "label": _("Selling Amount Foreign Currency"),
            "fieldname": "total",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        "conversion_rate": {
            "label": _("Exchange Rate"),
            "fieldname": "conversion_rate",
            "fieldtype": "Float",
            "width": 120,
        },
        "base_amount": {
            "label": _("Selling Amount INR"),
            "fieldname": "selling_amount",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 100,
        },
        "base_rate": {
            "label": _("Per KG Rate INR"),
            "fieldname": "base_rate",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 100,
        },
        "buying_rate": {
            "label": _("Valuation Rate"),
            "fieldname": "valuation_rate",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 100,
        },
        "buying_amount": {
            "label": _("Buying Amount"),
            "fieldname": "buying_amount",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 100,
        },
        "gross_profit": {
            "label": _("Gross Profit"),
            "fieldname": "gross_profit",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 100,
        },
        "gross_profit_percent": {
            "label": _("Gross Profit Percent"),
            "fieldname": "gross_profit_%",
            "fieldtype": "Percent",
            "width": 100,
        },
        "no_of_packages": {
            "label": _("Packing Material Qty"),
            "fieldname": "no_of_packages",
            "fieldtype": "Int",
            "width": 120,
        },
        "packaging_material": {
            "label": _("Packing Material Type"),
            "fieldname": "packaging_material",
            "fieldtype": "Link",
            "options": "Packaging Material",
            "width": 120,
        },
        "debit_in_account_currency": {
            "label": _("Loading Unloading Charges"),
            "fieldname": "debit_in_account_currency",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 120,
        },
        "insurance_charges": {
            "label": _("Insurance (Marine) - UCPL"),
            "fieldname": "insurance_charges",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 120,
        },
        # "foreign_bank_charges": {
        #     "label": _("Foreign Bank Charges INR"),
        #     "fieldname": "foreign_bank_charges",
        #     "fieldtype": "Currency",
        #     "options": "company_currency",
        #     "width": 180,
        # },
        "indirect_expence": {
            "label": _("Indirect Expense"),
            "fieldname": "indirect_expence",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 120,
        },
        "per_kg_indirect_expense": {
            "label": _("Per Kg Indirect Expense"),
            "fieldname": "per_kg_indirect_expense",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 120,
        },
        "buying_plus_indirect": {
            "label": _("Buying Amount + Indirect Expense"),
            "fieldname": "buying_plus_indirect",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 120,
        },
        "per_kg_cost": {
            "label": _("Per Kg Cost"),
            "fieldname": "per_kg_cost",
            "fieldtype": "Currency",
            "options": "company_currency",
            "width": 120,
        },
    })

    for col in group_wise_columns.get(scrub(filters.group_by)):
        col_def = column_map.get(col)
        if col_def:
            columns.append(col_def)
       
    if expence_head_columns:
        columns.extend(expence_head_columns)

    # Add charge columns for non-Invoice groupings
    if filters.group_by != "Invoice":
        columns.extend([
            {
                "label": _("Loading Unloading Charges"),
                "fieldname": "debit_in_account_currency",
                "fieldtype": "Currency",
                "options": "company_currency",
                "width": 120,
            },
            {
                "label": _("Insurance (Marine) - UCPL"),
                "fieldname": "insurance_charges",
                "fieldtype": "Currency",
                "options": "company_currency",
                "width": 120,
            },
            # {
            #     "label": _("Foreign Bank Charges INR"),
            #     "fieldname": "foreign_bank_charges",
            #     "fieldtype": "Currency",
            #     "options": "company_currency",
            #     "width": 180,
            # },
        ])

    columns.append({
        "fieldname": "currency",
        "label": _("Currency"),
        "fieldtype": "Link",
        "options": "Currency",
        "hidden": 1,
    })

    columns.append({
        "fieldname": "company_currency",
        "label": _("Company Currency"),
        "fieldtype": "Link",
        "options": "Currency",
        "hidden": 1,
    })

    return columns


def get_column_names():
    return frappe._dict({
        "invoice_or_item": "sales_invoice",
        "posting_date": "posting_date",
        "warehouse": "warehouse",
        "customer": "customer",
        "description": "description",
        "final_destination": "final_destination",
        "shipping_terms": "shipping_terms",
        "customer_group": "customer_group",
        "item_group": "item_group",
        "qty": "qty",
        "currency": "currency",
        "company_currency": "company_currency",
        "rate": "rate",
        "total": "total",
        "conversion_rate": "conversion_rate",
        "base_amount": "selling_amount",
        "base_rate": "base_rate",
        "buying_rate": "valuation_rate",
        "buying_amount": "buying_amount",
        "gross_profit": "gross_profit",
        "gross_profit_percent": "gross_profit_%",
        "no_of_packages": "no_of_packages",
        "packaging_material": "packaging_material",
        "debit_in_account_currency": "debit_in_account_currency",
        "insurance_charges": "insurance_charges",
        # "foreign_bank_charges": "foreign_bank_charges",
        "indirect_expence": "indirect_expence",
        "per_kg_indirect_expense": "per_kg_indirect_expense",
        "buying_plus_indirect": "buying_plus_indirect",
        "per_kg_cost": "per_kg_cost",
    })


class GrossProfitGenerator(object):
    def __init__(self, filters=None):
        self.data = []
        self.average_buying_rate = {}
        self.filters = frappe._dict(filters)
        self.load_invoice_items()

        if filters.group_by == "Invoice":
            self.group_items_by_invoice()

        self.load_stock_ledger_entries()
        self.load_product_bundle()
        self.load_non_stock_items()
        self.get_returned_invoice_items()
        self.process()
        self.final_data()

    def load_invoice_items(self):
        conditions = ""
        if self.filters.company:
            conditions += " and company = %(company)s"
        if self.filters.from_date:
            conditions += " and posting_date >= %(from_date)s"
        if self.filters.to_date:
            conditions += " and posting_date <= %(to_date)s"

        if self.filters.group_by == "Sales Person":
            sales_person_cols = ", sales.sales_person, sales.allocated_amount, sales.incentives"
            sales_team_table = "left join `tabSales Team` sales on sales.parent = `tabSales Invoice`.name"
        else:
            sales_person_cols = ""
            sales_team_table = ""

        if self.filters.get("sales_invoice"):
            conditions += " and `tabSales Invoice`.name = %(sales_invoice)s"
        if self.filters.get("item_code"):
            conditions += " and `tabSales Invoice Item`.item_code = %(item_code)s"

        self.si_list = frappe.db.sql("""
            select
                `tabSales Invoice Item`.parenttype,
                `tabSales Invoice Item`.parent,
                `tabSales Invoice`.posting_date,
                `tabSales Invoice`.shipping_terms,
                `tabSales Invoice`.posting_time,
                `tabSales Invoice`.project,
                `tabSales Invoice`.update_stock,
                `tabSales Invoice`.customer,
                `tabSales Invoice`.customer_group,
                `tabSales Invoice`.territory,
                `tabSales Invoice Item`.item_code,
                `tabSales Invoice Item`.item_name,
                `tabSales Invoice Item`.description,
                `tabSales Invoice Item`.warehouse,
                `tabSales Invoice Item`.item_group,
                `tabSales Invoice Item`.brand,
                `tabSales Invoice Item`.dn_detail,
                `tabSales Invoice Item`.delivery_note,
                `tabSales Invoice Item`.stock_qty as qty,
                `tabSales Invoice Item`.base_net_rate,
                `tabSales Invoice Item`.base_net_amount,
                `tabSales Invoice Item`.name as "item_row",
                `tabSales Invoice`.is_return,
                `tabSales Invoice`.final_destination,
                `tabSales Invoice Item`.cost_center,
                `tabSales Invoice`.conversion_rate,
                `tabSales Invoice`.currency,
                `tabSales Invoice`.total,
                `tabSales Invoice Item`.rate,
                `tabSales Invoice Item`.no_of_packages,
                `tabSales Invoice Item`.packaging_material
            from
                `tabSales Invoice`
            inner join
                `tabSales Invoice Item` on `tabSales Invoice Item`.parent = `tabSales Invoice`.name
            {sales_team_table}
            where
                `tabSales Invoice`.docstatus = 1
                and `tabSales Invoice`.is_opening != 'Yes'
                {conditions}
                {match_cond}
            order by
                `tabSales Invoice`.posting_date desc,
                `tabSales Invoice`.posting_time desc
        """.format(
            conditions=conditions,
            sales_team_table=sales_team_table,
            match_cond=get_match_cond("Sales Invoice"),
        ), self.filters, as_dict=1)

    def final_data(self):
        indirect_expence_dict = {}

        indirect_expence_data = frappe.db.sql("""
            SELECT
                si.name as sales_invoice, sum(pi.base_total) as net_total
            FROM
                `tabPurchase Invoice` as pi
                LEFT JOIN `tabSales Invoice` as si on pi.sales_invoice = si.name and si.docstatus = 1
            WHERE
                pi.docstatus = 1 and pi.sales_invoice is not null and pi.sales_invoice != ''
            group by si.name
        """, as_dict=1)

        for row in indirect_expence_data:
            indirect_expence_dict[row.sales_invoice] = row.net_total

        si_amount_dict = {}
        
        for row in self.si_list:
            if (hasattr(row, 'indent') and row.indent == 0 and indirect_expence_dict.get(row.invoice_or_item)):
                si_amount_dict[row.invoice_or_item] = {
                    'total_base_amount': (row.base_amount - row.buying_amount), 
                    'total_indirect_expence': indirect_expence_dict.get(row.invoice_or_item)
                }
            elif indirect_expence_dict.get(row.parent) and self.filters.get("group_by") != "Invoice":
                si_amount_dict[row.parent] = {
                    'total_base_amount': (row.base_amount - row.buying_amount), 
                    'total_indirect_expence': indirect_expence_dict.get(row.parent, 0)
                }

        invoice_list = []

        for row in self.si_list[::-1]:
            if si_amount_dict.get(row.invoice_or_item):
                row.indirect_expence = (si_amount_dict[row.invoice_or_item]["total_indirect_expence"] * (row.base_amount - row.buying_amount)) / si_amount_dict[row.invoice_or_item]["total_base_amount"]
                row.gross_profit = row.gross_profit - row.indirect_expence
                if row.base_amount:
                    row.gross_profit_percent = flt((row.gross_profit / row.base_amount) * 100.0, 2)
                else:
                    row.gross_profit_percent = 0.0
    
            elif si_amount_dict.get(row.parent_invoice):
                row.indirect_expence = (si_amount_dict[row.parent_invoice]["total_indirect_expence"] * (row.base_amount - row.buying_amount)) / si_amount_dict[row.parent_invoice]["total_base_amount"]
                row.gross_profit = row.gross_profit - (si_amount_dict[row.parent_invoice]["total_indirect_expence"] * (row.base_amount - row.buying_amount)) / si_amount_dict[row.parent_invoice]["total_base_amount"]
                if row.base_amount:
                    row.gross_profit_percent = flt((row.gross_profit / row.base_amount) * 100.0, 2)
                else:
                    row.gross_profit_percent = 0.0

            elif self.filters.get("group_by") != "Invoice" and si_amount_dict.get(row.parent):
                if row.item_code not in invoice_list:
                    if row.get('base_amount') or row.get('buying_amount'):
                        row.gross_profit = row.gross_profit - (si_amount_dict[row.parent]['total_indirect_expence'] * (row.get('base_amount') - row.get('buying_amount')) / (row.get('base_amount') - row.get('buying_amount')))
                    else:
                        row.gross_profit = row.gross_profit
                    if row.base_amount:
                        row.gross_profit_percent = flt((row.gross_profit / row.base_amount) * 100.0, 2)
                    else:
                        row.gross_profit_percent = 0.0
                    invoice_list.append(row.item_code)
            else:
                row.indirect_expence = 0

    def process(self):
        self.grouped = {}
        self.grouped_data = []

        self.currency_precision = cint(frappe.db.get_default("currency_precision")) or 3
        self.float_precision = cint(frappe.db.get_default("float_precision")) or 2

        grouped_by_invoice = True if self.filters.get("group_by") == "Invoice" else False

        if grouped_by_invoice:
            buying_amount = 0

        for row in reversed(self.si_list):
            if self.skip_row(row):
                continue

            row.base_amount = flt(row.base_net_amount, self.currency_precision)
            row.currency = row.currency
            row.company_currency = self.filters.currency

            product_bundles = []
            if row.update_stock:
                product_bundles = self.product_bundles.get(row.parenttype, {}).get(row.parent, frappe._dict())
            elif row.dn_detail:
                product_bundles = self.product_bundles.get("Delivery Note", {}).get(row.delivery_note, frappe._dict())
                row.item_row = row.dn_detail

            # get buying amount
            if row.item_code in product_bundles:
                row.buying_amount = flt(self.get_buying_amount_from_product_bundle(row, product_bundles[row.item_code]), self.currency_precision)
            else:
                row.buying_amount = flt(self.get_buying_amount(row, row.item_code), self.currency_precision)

            if grouped_by_invoice:
                if hasattr(row, 'indent') and row.indent == 1.0:
                    buying_amount += row.buying_amount
                elif hasattr(row, 'indent') and row.indent == 0.0:
                    row.buying_amount = buying_amount
                    buying_amount = 0

            # get buying rate
            if flt(row.qty):
                row.buying_rate = flt(row.buying_amount / flt(row.qty), self.float_precision)
                row.base_rate = flt(row.base_amount / flt(row.qty), self.float_precision)
            else:
                if self.is_not_invoice_row(row):
                    row.buying_rate, row.base_rate = 0.0, 0.0

            # calculate gross profit
            row.gross_profit = flt(row.base_amount - row.buying_amount, self.currency_precision)
            if row.base_amount:
                row.gross_profit_percent = flt((row.gross_profit / row.base_amount) * 100.0, self.currency_precision)
            else:
                row.gross_profit_percent = 0.0

            # add to grouped
            self.grouped.setdefault(row.get(scrub(self.filters.group_by)), []).append(row)

        if self.grouped:
            self.get_average_rate_based_on_group_by()

    def get_average_rate_based_on_group_by(self):
        for key in list(self.grouped):
            if self.filters.get("group_by") != "Invoice":
                for i, row in enumerate(self.grouped[key]):
                    if i == 0:
                        new_row = row
                    else:
                        new_row.qty += flt(row.qty)
                        new_row.buying_amount += flt(row.buying_amount, self.currency_precision)
                        new_row.base_amount += flt(row.base_amount, self.currency_precision)
                new_row = self.set_average_rate(new_row)
                self.grouped_data.append(new_row)
            else:
                for i, row in enumerate(self.grouped[key]):
                    if hasattr(row, 'indent') and row.indent == 1.0:
                        if (row.parent in self.returned_invoices and row.item_code in self.returned_invoices[row.parent]):
                            returned_item_rows = self.returned_invoices[row.parent][row.item_code]
                            for returned_item_row in returned_item_rows:
                                row.qty += flt(returned_item_row.qty)
                                row.base_amount += flt(returned_item_row.base_amount, self.currency_precision)
                            row.buying_amount = flt(flt(row.qty) * flt(row.buying_rate), self.currency_precision)
                        if flt(row.qty) or row.base_amount:
                            row = self.set_average_rate(row)
                            self.grouped_data.append(row)

    def is_not_invoice_row(self, row):
        return (self.filters.get("group_by") == "Invoice" and hasattr(row, 'indent') and row.indent != 0.0) or self.filters.get("group_by") != "Invoice"

    def set_average_rate(self, new_row):
        self.set_average_gross_profit(new_row)
        new_row.buying_rate = flt(new_row.buying_amount / new_row.qty, self.float_precision) if new_row.qty else 0
        new_row.base_rate = flt(new_row.base_amount / new_row.qty, self.float_precision) if new_row.qty else 0
        return new_row

    def set_average_gross_profit(self, new_row):
        new_row.gross_profit = flt(new_row.base_amount - new_row.buying_amount, self.currency_precision)
        new_row.gross_profit_percent = flt(((new_row.gross_profit / new_row.base_amount) * 100.0), self.currency_precision) if new_row.base_amount else 0
        new_row.buying_rate = flt(new_row.buying_amount / flt(new_row.qty), self.float_precision) if flt(new_row.qty) else 0
        new_row.base_rate = flt(new_row.base_amount / flt(new_row.qty), self.float_precision) if flt(new_row.qty) else 0

    def get_returned_invoice_items(self):
        returned_invoices = frappe.db.sql("""
            select
                si.name, si_item.item_code, si_item.stock_qty as qty, si_item.base_net_amount as base_amount, si.return_against
            from
                `tabSales Invoice` si, `tabSales Invoice Item` si_item
            where
                si.name = si_item.parent
                and si.docstatus = 1
                and si.is_return = 1
        """, as_dict=1)

        self.returned_invoices = frappe._dict()
        for inv in returned_invoices:
            self.returned_invoices.setdefault(inv.return_against, frappe._dict()).setdefault(inv.item_code, []).append(inv)

    def skip_row(self, row):
        if self.filters.get("group_by") != "Invoice":
            if not row.get(scrub(self.filters.get("group_by", ""))):
                return True
        return False

    def get_buying_amount_from_product_bundle(self, row, product_bundle):
        buying_amount = 0.0
        for packed_item in product_bundle:
            if packed_item.get("parent_detail_docname") == row.item_row:
                buying_amount += self.get_buying_amount(row, packed_item.item_code)
        return flt(buying_amount, self.currency_precision)

    def get_buying_amount(self, row, item_code):
        if item_code in self.non_stock_items and (row.project or row.cost_center):
            item_rate = self.get_last_purchase_rate(item_code, row)
            return flt(row.qty) * item_rate
        else:
            my_sle = self.sle.get((item_code, row.warehouse))
            if (row.update_stock or row.dn_detail) and my_sle:
                parenttype, parent = row.parenttype, row.parent
                if row.dn_detail:
                    parenttype, parent = "Delivery Note", row.delivery_note

                for i, sle in enumerate(my_sle):
                    if (sle.voucher_type == parenttype and parent == sle.voucher_no and sle.voucher_detail_no == row.item_row):
                        previous_stock_value = len(my_sle) > i + 1 and flt(my_sle[i + 1].stock_value) or 0.0
                        if previous_stock_value:
                            return (previous_stock_value - flt(sle.stock_value)) * flt(row.qty) / abs(flt(sle.qty))
                        else:
                            return flt(row.qty) * self.get_average_buying_rate(row, item_code)
            else:
                return flt(row.qty) * self.get_average_buying_rate(row, item_code)
        return 0.0

    def get_average_buying_rate(self, row, item_code):
        args = row
        if not item_code in self.average_buying_rate:
            args.update({
                "voucher_type": row.parenttype,
                "voucher_no": row.parent,
                "allow_zero_valuation": True,
                "company": self.filters.company,
                "qty": row.qty,
                "serial_no": None,
                "batch_no": None,
                "posting_date": row.posting_date,
                "posting_time": row.posting_time if hasattr(row, 'posting_time') else None
            })
            try:
                average_buying_rate = get_incoming_rate(args)
                self.average_buying_rate[item_code] = flt(average_buying_rate) if average_buying_rate else 0.0
            except Exception as e:
                frappe.log_error(f"Error in get_average_buying_rate for item {item_code}: {str(e)}")
                self.average_buying_rate[item_code] = 0.0
        return self.average_buying_rate.get(item_code, 0.0)

    def get_last_purchase_rate(self, item_code, row):
        try:
            purchase_invoice = frappe.qb.DocType("Purchase Invoice")
            purchase_invoice_item = frappe.qb.DocType("Purchase Invoice Item")

            query = (
                frappe.qb.from_(purchase_invoice_item)
                .inner_join(purchase_invoice)
                .on(purchase_invoice.name == purchase_invoice_item.parent)
                .select(purchase_invoice_item.base_rate / purchase_invoice_item.conversion_factor)
                .where(purchase_invoice.docstatus == 1)
                .where(purchase_invoice.posting_date <= self.filters.to_date)
                .where(purchase_invoice_item.item_code == item_code)
            )

            if row.project:
                query.where(purchase_invoice_item.project == row.project)
            if row.cost_center:
                query.where(purchase_invoice_item.cost_center == row.cost_center)

            query.orderby(purchase_invoice.posting_date, order=frappe.qb.desc)
            query.limit(1)
            last_purchase_rate = query.run()

            return flt(last_purchase_rate[0][0]) if last_purchase_rate and last_purchase_rate[0][0] else 0
        except Exception as e:
            frappe.log_error(f"Error in get_last_purchase_rate for item {item_code}: {str(e)}")
            return 0

    def group_items_by_invoice(self):
        parents = []
        for row in self.si_list:
            if row.parent not in parents:
                parents.append(row.parent)

        parents_index = 0
        for index, row in enumerate(self.si_list):
            if parents_index < len(parents) and row.parent == parents[parents_index]:
                invoice = self.get_invoice_row(row)
                self.si_list.insert(index, invoice)
                parents_index += 1
            else:
                if not hasattr(row, 'indent') or not row.indent:
                    row.indent = 1.0
                    row.parent_invoice = row.parent
                    row.invoice_or_item = row.item_code
                    if frappe.db.exists("Product Bundle", row.item_code):
                        self.add_bundle_items(row, index)

    def get_invoice_row(self, row):
        return frappe._dict({
            "parent_invoice": "",
            "indent": 0.0,
            "invoice_or_item": row.parent,
            "parent": None,
            "posting_date": row.posting_date,
            "posting_time": row.posting_time,
            "project": row.project,
            "update_stock": row.update_stock,
            "customer": row.customer,
            "customer_group": row.customer_group,
            "item_code": None,
            "item_name": None,
            "description": row.description,
            "warehouse": None,
            "item_group": None,
            "brand": None,
            "dn_detail": None,
            "delivery_note": None,
            "qty": None,
            "item_row": None,
            "is_return": row.is_return,
            "cost_center": row.cost_center,
            "final_destination": row.final_destination,
            "shipping_terms": row.shipping_terms,
            "conversion_rate": row.conversion_rate,
            "currency": row.currency,
            "total": row.total,
            "rate": row.rate,
            "no_of_packages": row.no_of_packages,
            "packaging_material": row.packaging_material,
            "base_net_amount": frappe.db.get_value("Sales Invoice", row.parent, "base_net_total") or 0,
        })

    def add_bundle_items(self, product_bundle, index):
        bundle_items = self.get_bundle_items(product_bundle)
        for i, item in enumerate(bundle_items):
            bundle_item = self.get_bundle_item_row(product_bundle, item)
            self.si_list.insert((index + i + 1), bundle_item)

    def get_bundle_items(self, product_bundle):
        return frappe.get_all("Product Bundle Item", filters={"parent": product_bundle.item_code}, fields=["item_code", "qty"])

    def get_bundle_item_row(self, product_bundle, item):
        item_name, description, item_group, brand = self.get_bundle_item_details(item.item_code)
        return frappe._dict({
            "parent_invoice": product_bundle.item_code,
            "indent": product_bundle.indent + 1,
            "parent": None,
            "invoice_or_item": item.item_code,
            "posting_date": product_bundle.posting_date,
            "posting_time": product_bundle.posting_time,
            "project": product_bundle.project,
            "customer": product_bundle.customer,
            "customer_group": product_bundle.customer_group,
            "item_code": item.item_code,
            "item_name": item_name,
            "description": description,
            "warehouse": product_bundle.warehouse,
            "item_group": item_group,
            "brand": brand,
            "dn_detail": product_bundle.dn_detail,
            "delivery_note": product_bundle.delivery_note,
            "qty": (flt(product_bundle.qty) * flt(item.qty)),
            "item_row": None,
            "is_return": product_bundle.is_return,
            "cost_center": product_bundle.cost_center,
        })

    def get_bundle_item_details(self, item_code):
        return frappe.db.get_value("Item", item_code, ["item_name", "description", "item_group", "brand"])

    def load_stock_ledger_entries(self):
        res = frappe.db.sql("""
            select item_code, voucher_type, voucher_no, voucher_detail_no, stock_value, warehouse, actual_qty as qty
            from `tabStock Ledger Entry`
            where company=%(company)s and is_cancelled = 0
            order by item_code desc, warehouse desc, posting_date desc, posting_time desc, creation desc
        """, self.filters, as_dict=True)
        
        self.sle = {}
        for r in res:
            if (r.item_code, r.warehouse) not in self.sle:
                self.sle[(r.item_code, r.warehouse)] = []
            self.sle[(r.item_code, r.warehouse)].append(r)

    def load_product_bundle(self):
        self.product_bundles = {}
        for d in frappe.db.sql("""
            select parenttype, parent, parent_item, item_code, warehouse, -1*qty as total_qty, parent_detail_docname
            from `tabPacked Item` where docstatus=1
        """, as_dict=True):
            self.product_bundles.setdefault(d.parenttype, frappe._dict()).setdefault(d.parent, frappe._dict()).setdefault(d.parent_item, []).append(d)

    def load_non_stock_items(self):
        self.non_stock_items = frappe.db.sql_list("select name from tabItem where is_stock_item=0")