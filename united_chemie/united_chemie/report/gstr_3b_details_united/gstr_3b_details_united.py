# Copyright (c) 2023, Resilient Tech and contributors
# For license information, please see license.txt

from dateutil.relativedelta import relativedelta

import frappe
from erpnext.controllers.trends import get_period_date_ranges
from frappe import _
from frappe.utils import cstr, getdate

from india_compliance.gst_india.utils.gstr3b.gstr3b_inward_data import (
    INWARD_SECTION_SUB_CATEGORY_MAP,
    GSTR3BInwardInvoices,
)


def execute(filters=None):
    return BaseGSTR3BDetails(filters).run()


class BaseGSTR3BDetails:
    def __init__(self, filters=None):
        self.filters = frappe._dict(filters or {})
        self.company = self.filters.company
        self.company_gstin = self.filters.company_gstin
        self.company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
        self.filter_by = self.filters.filter_by or "ITC Claim Period"
        self.sub_section = cstr(self.filters.sub_section)
        self.from_date = None
        self.to_date = None

    def run(self):
        self.validate_filters()
        self.set_date_range()
        periods = self.get_periods()
        return self.get_columns(periods), self.add_period_data(self.get_data(), periods)

    def validate_filters(self):
        if not self.sub_section:
            frappe.throw(_("Please select a sub section to view details"))
        if self.sub_section not in INWARD_SECTION_SUB_CATEGORY_MAP:
            frappe.throw(_("Invalid sub section selected"))

        filter_based_on = self.filters.filter_based_on or "Fiscal Year"
        if filter_based_on == "Fiscal Year" and not self.filters.fiscal_year:
            frappe.throw(_("Please select a Fiscal Year"))
        if filter_based_on == "Date Range":
            if not self.filters.from_date or not self.filters.to_date:
                frappe.throw(_("Please select both From Date and To Date"))
            if getdate(self.filters.from_date) > getdate(self.filters.to_date):
                frappe.throw(_("From Date cannot be after To Date"))
        if not self.filters.period:
            frappe.throw(_("Please select a Period"))

    def set_date_range(self):
        if (self.filters.filter_based_on or "Fiscal Year") == "Date Range":
            self.from_date = getdate(self.filters.from_date)
            self.to_date = getdate(self.filters.to_date)
            return

        self.from_date, self.to_date = frappe.get_cached_value(
            "Fiscal Year", self.filters.fiscal_year, ["year_start_date", "year_end_date"]
        )
        self.from_date = getdate(self.from_date)
        self.to_date = getdate(self.to_date)

    def get_periods(self):
        if (self.filters.filter_based_on or "Fiscal Year") == "Fiscal Year":
            return [
                (getdate(start_date), getdate(end_date))
                for start_date, end_date in get_period_date_ranges(
                    self.filters.period, self.filters.fiscal_year
                )
            ]

        months = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}[self.filters.period]
        start_date, periods = self.from_date, []
        while start_date <= self.to_date:
            end_date = min(start_date + relativedelta(months=months, days=-1), self.to_date)
            periods.append((start_date, end_date))
            start_date = end_date + relativedelta(days=1)
        return periods

    def get_inward_filters(self):
        return frappe._dict(
            company=self.company,
            company_gstin=self.company_gstin,
            from_date=self.from_date,
            to_date=self.to_date,
            filter_by=self.filter_by,
        )

    def get_filtered_inward_data(self):
        return GSTR3BInwardInvoices(self.get_inward_filters()).get_section_data(
            self.sub_section,
            group_by_invoice=True,
            invoice_sub_categories=self.filters.invoice_sub_category,
        )

    def get_data(self):
        data = sorted(
            self.get_filtered_inward_data(),
            key=lambda row: (row["invoice_sub_category"], row["posting_date"]),
        )
        return self.add_purchase_invoice_details(data)

    def add_purchase_invoice_details(self, data):
        """Add the Purchase Invoice fields available in the 2B matching details report."""
        voucher_nos = list({row.get("voucher_no") for row in data if row.get("voucher_no")})
        if not voucher_nos:
            return data

        invoice_meta = frappe.get_meta("Purchase Invoice")
        fields = [
            "supplier",
            "against_expense_account",
            "bill_date",
            "bill_no",
            "tax_category",
            "net_total",
        ]
        for fieldname in (
            "supplier_gstin",
            "itc_eligibility",
            "itc_classification",
            "gst_category",
            "itc_claim_period",
        ):
            if invoice_meta.has_field(fieldname):
                fields.append(fieldname)

        invoices = frappe.get_all(
            "Purchase Invoice", filters={"name": ["in", voucher_nos]}, fields=["name", *fields]
        )
        invoices_by_name = {invoice.name: invoice for invoice in invoices}

        for row in data:
            invoice = invoices_by_name.get(row.get("voucher_no"))
            if not invoice:
                continue
            for fieldname in fields:
                if invoice.get(fieldname) is not None:
                    row[fieldname] = invoice.get(fieldname)

        return data

    def add_period_data(self, data, periods):
        amount_fields = self.get_amount_fields()
        for row in data:
            allocation_date = self.get_allocation_date(row)
            for period_index, (start_date, end_date) in enumerate(periods):
                for fieldname in amount_fields:
                    row[f"period_{period_index}_{fieldname}"] = 0
                if start_date <= allocation_date <= end_date:
                    for fieldname in amount_fields:
                        row[f"period_{period_index}_{fieldname}"] = row.get(fieldname, 0)
            for fieldname in amount_fields:
                row[f"total_{fieldname}"] = row.get(fieldname, 0)
        return data

    def get_allocation_date(self, row):
        """Use the same date basis as the report's Filter By selection."""
        if self.filter_by == "ITC Claim Period":
            claim_period = row.get("itc_claim_period")
            if claim_period and len(claim_period) == 6 and claim_period.isdigit():
                # ITC Claim Period is stored as MMYYYY, e.g. 092026.
                return getdate(f"{claim_period[2:]}-{claim_period[:2]}-01")

        return getdate(row["posting_date"])

    def get_columns(self, periods):
        columns = [
			{"fieldname": "supplier_gstin", "label": _("Supplier GSTIN"), "fieldtype": "Data", "width": 150},
			{"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier", "width": 180},
            {
                "fieldname": "against_expense_account",
                "label": _("Against Expense Account"),
                "fieldtype": "Small Text",
                "width": 180,
            },
            {"fieldname": "bill_date", "label": _("Supplier Invoice Date"), "fieldtype": "Date", "width": 120},
            {"fieldname": "bill_no", "label": _("Supplier Invoice No"), "fieldtype": "Data", "width": 150},
            {"fieldname": "tax_category", "label": _("Tax Category"), "fieldtype": "Link", "options": "Tax Category", "width": 130},
			{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date", "width": 100},
			{"fieldname": "itc_eligibility", "label": _("ITC Eligibility"), "fieldtype": "Data", "width": 150},
            {"fieldname": "itc_classification", "label": _("ITC Classification"), "fieldtype": "Data", "width": 150},
            {"fieldname": "gst_category", "label": _("GST Category"), "fieldtype": "Data", "width": 130},
			{"fieldname": "voucher_type", "label": _("Voucher Type"), "fieldtype": "Data", "width": 100},
            {"fieldname": "voucher_no", "label": _("Voucher No"), "fieldtype": "Dynamic Link", "options": "voucher_type"},
            {
                "fieldname": "net_total",
                "label": _("Net Total"),
                "fieldtype": "Currency",
                "options": self.company_currency,
                "width": 120,
            },
           
        ]
        for period_index, (start_date, end_date) in enumerate(periods):
            period_label = self.get_period_label(start_date, end_date)
            for fieldname, label in self.get_amount_field_details():
                columns.append({
                    "fieldname": f"period_{period_index}_{fieldname}",
                    "label": _("{0} ({1})").format(period_label, label),
                    "fieldtype": "Currency", "options": self.company_currency, "width": 120,
                })
        for fieldname, label in self.get_amount_field_details():
            columns.append({
                "fieldname": f"total_{fieldname}", "label": _("Total {0}").format(label),
                "fieldtype": "Currency", "options": self.company_currency, "width": 120,
            })
        columns.append({
            "fieldname": "invoice_sub_category",
            "label": _("Eligibility for ITC") if self.sub_section == "4" else _("Nature of Supply"),
            "fieldtype": "Data", "width": 150,
        })
        return columns

    def get_amount_field_details(self):
        if self.sub_section == "4":
            return [
                ("igst_amount", _("Integrated Tax")), ("cgst_amount", _("Central Tax")),
                ("sgst_amount", _("State/UT Tax")), ("cess_amount", _("Cess Tax")),
            ]
        return [("intra", _("Intra State")), ("inter", _("Inter State"))]

    def get_amount_fields(self):
        return [fieldname for fieldname, _label in self.get_amount_field_details()]

    @staticmethod
    def get_period_label(start_date, end_date):
        start_date, end_date = getdate(start_date), getdate(end_date)
        if start_date.month == end_date.month:
            return start_date.strftime("%b")
        return f"{start_date.strftime('%b')}-{end_date.strftime('%b')}"