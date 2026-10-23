// Copyright (c) 2023, Resilient Tech and contributors
// For license information, please see license.txt
/* eslint-disable */

const AMOUNT_FIELDS = ["igst_amount", "cgst_amount", "sgst_amount", "cess_amount", "intra", "inter"];

frappe.query_reports["GSTR-3B Details-United"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1, default: frappe.defaults.get_user_default("Company") },
        {
            fieldname: "company_gstin", label: __("Company GSTIN"), fieldtype: "Autocomplete", reqd: 1,
            get_query: () => india_compliance.get_gstin_query(frappe.query_report.get_filter_value("company")),
        },
        {
            fieldname: "filter_based_on", label: __("Filter Based On"), fieldtype: "Select",
            options: ["Fiscal Year", "Date Range"], default: "Fiscal Year", reqd: 1,
            on_change: () => toggle_date_filters(),
        },
        {
            fieldname: "fiscal_year", label: __("Fiscal Year"), fieldtype: "Link", options: "Fiscal Year",
            default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),
            depends_on: "eval:doc.filter_based_on == 'Fiscal Year'",
            mandatory_depends_on: "eval:doc.filter_based_on == 'Fiscal Year'",
        },
        {
            fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
            depends_on: "eval:doc.filter_based_on == 'Date Range'",
            mandatory_depends_on: "eval:doc.filter_based_on == 'Date Range'",
        },
        {
            fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
            depends_on: "eval:doc.filter_based_on == 'Date Range'",
            mandatory_depends_on: "eval:doc.filter_based_on == 'Date Range'",
        },
        {
            fieldname: "period", label: __("Period"), fieldtype: "Select",
            options: ["Monthly", "Quarterly", "Half-Yearly", "Yearly"], default: "Monthly", reqd: 1,
        },
        {
            fieldname: "filter_by", label: __("Filter By"), fieldtype: "Select", default: "ITC Claim Period",
            options: ["ITC Claim Period", "Posting Date"], reqd: 1,
        },
        {
            fieldname: "sub_section", label: __("Sub Section"), fieldtype: "Select", reqd: 1, default: "4",
            options: [
                { value: "4", label: __("4. Eligible ITC") },
                { value: "5", label: __("5. Values of exempt, nil rated and non-GST inward supplies") },
            ],
            on_change: () => frappe.query_report.set_filter_value("invoice_sub_category", []),
        },
        { fieldtype: "MultiSelectList", fieldname: "invoice_sub_category", label: __("Invoice Sub Category"), get_data: () => get_subcategory_options() },
    ],

    onload() { toggle_date_filters(); },
    get_datatable_options(datatable_options) {
        datatable_options.hooks = { columnTotal: custom_report_column_total };
        return datatable_options;
    },
};

function toggle_date_filters() {
    const is_date_range = frappe.query_report.get_filter_value("filter_based_on") === "Date Range";
    // toggle_filter_display's second parameter hides the filter.
    frappe.query_report.toggle_filter_display("fiscal_year", is_date_range);
    frappe.query_report.toggle_filter_display("from_date", !is_date_range);
    frappe.query_report.toggle_filter_display("to_date", !is_date_range);
}

function get_subcategory_options() {
    return india_compliance.get_inward_subcategory_options(frappe.query_report.get_filter_value("sub_section"));
}

function custom_report_column_total(...args) {
    const column_field = args[1].column.fieldname;
    const base_field = column_field.replace(/^period_\d+_/, "").replace(/^total_/, "");
    if (!AMOUNT_FIELDS.includes(base_field)) return;
    const { data } = this.datamanager;
    return this.datamanager.getFilteredRowIndices().reduce((acc, index) => {
        const row = data[index];
        const value = row[column_field] || 0;
        return row.invoice_category === "ITC Reversed" ? acc - value : acc + value;
    }, 0);
}