app_name = "united_chemie"
app_title = "United Chemie"
app_publisher = "Finbyz Tech Pvt Ltd"
app_description = "Custom app for United Chemie"
app_email = "info@finbyz.tech"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/united_chemie/css/united_chemie.css"
# app_include_js = "/assets/united_chemie/js/united_chemie.js"

# include js, css files in header of web template
# web_include_css = "/assets/united_chemie/css/united_chemie.css"
# web_include_js = "/assets/united_chemie/js/united_chemie.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "united_chemie/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Journal Entry" : "public/js/journal_entry.js",
    "BOM":"public/js/bom.js",
    "Asset" : "public/js/assets.js",
    "Sales Invoice" : "public/js/sales_invoice.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "united_chemie.utils.jinja_methods",
# 	"filters": "united_chemie.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "united_chemie.install.before_install"
# after_install = "united_chemie.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "united_chemie.uninstall.before_uninstall"
# after_uninstall = "united_chemie.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "united_chemie.utils.before_app_install"
# after_app_install = "united_chemie.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "united_chemie.utils.before_app_uninstall"
# after_app_uninstall = "united_chemie.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "united_chemie.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	# "ToDo": "custom_app.overrides.CustomToDo",
    "Payment Entry": "united_chemie.united_chemie.override.override_doctype_class.payment_entry.PaymentEntry",
    "Sales Order": "united_chemie.united_chemie.override.override_doctype_class.custom_sales_order.CustomSalesOrder",
    "Ball Mill Data Sheet" : "united_chemie.united_chemie.override.override_doctype_class.ball_mill_data_sheet.BallMillDataSheet",
    "Exchange Rate Revaluation": "united_chemie.united_chemie.override.override_doctype_class.exchange_rate_revaluation.CustomExchangeRateRevaluation"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Work Order": {
		"validate": "united_chemie.united_chemie.doc_events.work_order.validate",
        "on_submit": "united_chemie.united_chemie.doc_events.work_order.on_submit",
        "onload": "united_chemie.united_chemie.doc_events.work_order.onload",
	},
    "Sales Invoice": {
        "before_save": "united_chemie.united_chemie.doc_events.sales_invoice.before_save",
        "on_submit": "united_chemie.united_chemie.doc_events.sales_invoice.on_submit"
    },
    "Stock Entry": {
        "validate": "united_chemie.united_chemie.doc_events.stock_entry.validate",
    }
    # "Purchase Invoice": {
    #     "validate": "united_chemie.transaction.validate",
	# }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"united_chemie.tasks.all"
# 	],
# 	"daily": [
# 		"united_chemie.tasks.daily"
# 	],
# 	"hourly": [
# 		"united_chemie.tasks.hourly"
# 	],
# 	"weekly": [
# 		"united_chemie.tasks.weekly"
# 	],
# 	"monthly": [
# 		"united_chemie.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "united_chemie.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"erpnext.accounts.doctype.exchange_rate_revaluation.exchange_rate_revaluation.ExchangeRateRevaluation.make_jv_for_revaluation":
#         "united_chemie.united_chemie.override.override_doctype_class.exchange_rate_revaluation.CustomExchangeRateRevaluation.make_jv_for_revaluation"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "united_chemie.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["united_chemie.utils.before_request"]
# after_request = ["united_chemie.utils.after_request"]

# Job Events
# ----------
# before_job = ["united_chemie.utils.before_job"]
# after_job = ["united_chemie.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"united_chemie.auth.validate"
# ]
# from india_compliance.gst_india.overrides import transaction
# from united_chemie.transaction import validate_transaction as custom_validate_transaction
# transaction.validate_transaction = custom_validate_transaction

from united_chemie.transaction import custom_validate_item_wise_tax_detail
from india_compliance.gst_india.overrides import transaction
transaction.validate_item_wise_tax_detail = custom_validate_item_wise_tax_detail

from india_compliance.gst_india.doctype.bill_of_entry.bill_of_entry import BillofEntry
from united_chemie.united_chemie.doc_events.bill_of_entry import validate_taxes, set_total_taxes
BillofEntry.validate_taxes = validate_taxes
BillofEntry.set_total_taxes = set_total_taxes

from india_compliance.gst_india.overrides.transaction import ItemGSTDetails
from united_chemie.transaction import get_, get_item_tax_detail_, set_item_wise_tax_details_, update_item_tax_details_
ItemGSTDetails.get = get_
ItemGSTDetails.get_item_tax_detail = get_item_tax_detail_
ItemGSTDetails.set_item_wise_tax_details = set_item_wise_tax_details_
ItemGSTDetails.update_item_tax_details = update_item_tax_details_


from erpnext.assets.doctype.asset_depreciation_schedule import asset_depreciation_schedule
from united_chemie.united_chemie.override.asset import custom_get_depreciation_amount
asset_depreciation_schedule.get_depreciation_amount = custom_get_depreciation_amount
# from finbyzerp.finbyzerp.doc_events import stock_entry
from united_chemie.united_chemie.override.stock_entry_override import custom_create_quality_inspection_entry
stock_entry.create_quality_inspection_entry = custom_create_quality_inspection_entry

fixtures = [
       {
         "dt": "Custom Field", 
         "filters":[["module", "in", ['United Chemie']]]
      },
      {
            "dt": "Property Setter",
            "filters":[["module", "in", ['United Chemie']]]
      }
]