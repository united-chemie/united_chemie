// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Profit and Loss Statement-United"] = $.extend({}, erpnext.financial_statements);

erpnext.utils.add_dimensions("Profit and Loss Statement", 10);

frappe.query_reports["Profit and Loss Statement-United"]["filters"].push(
    {
        fieldname: "selected_view",
        label: ("Select View"),
        fieldtype: "Select",
        options: [
            { value: "Report", label: ("Report View") },
            { value: "Growth", label: ("Growth View") },
            { value: "Margin", label: ("Margin View") },
        ],
        default: "Report",
        reqd: 1,
    },
    {
        fieldname: "accumulated_values",
        label: ("Accumulated Values"),
        fieldtype: "Check",
        default: 0,
    },
    {
        fieldname: "include_default_book_entries",
        label: ("Include Default FB Entries"),
        fieldtype: "Check",
        default: 1,
    },
    {
        fieldname: "show_zero_values",
        label: __("Show zero values"),
        fieldtype: "Check",
    }
);