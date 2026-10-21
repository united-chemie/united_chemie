// Copyright (c) 2026, United Chemie and contributors
// For license information, please see license.txt

frappe.query_reports["Item Average Rate"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "filter_based_on",
			label: __("Filter Based On"),
			fieldtype: "Select",
			options: "Fiscal Year\nDate Range",
			default: "Fiscal Year",
			reqd: 1,
			on_change() {
				const filter_based_on = frappe.query_report.get_filter_value("filter_based_on");
				frappe.query_report.toggle_filter_display(
					"fiscal_year",
					filter_based_on === "Date Range"
				);
				frappe.query_report.toggle_filter_display(
					"from_date",
					filter_based_on === "Fiscal Year"
				);
				frappe.query_report.toggle_filter_display(
					"to_date",
					filter_based_on === "Fiscal Year"
				);
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),
			depends_on: "eval:doc.filter_based_on == 'Fiscal Year'",
			mandatory_depends_on: "eval:doc.filter_based_on == 'Fiscal Year'",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.filter_based_on == 'Date Range'",
			mandatory_depends_on: "eval:doc.filter_based_on == 'Date Range'",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.filter_based_on == 'Date Range'",
			mandatory_depends_on: "eval:doc.filter_based_on == 'Date Range'",
		},
		{
			fieldname: "period",
			label: __("Period"),
			fieldtype: "Select",
			options: "Monthly\nQuarterly\nHalf-Yearly\nYearly",
			default: "Monthly",
			reqd: 1,
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			get_query() {
				return { query: "erpnext.controllers.queries.item_query" };
			},
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "type",
			label: __("Type"),
			fieldtype: "Select",
			options: "Purchase Receipt\nManufacture",
			default: "Purchase Receipt",
			reqd: 1,
		},
	],
};