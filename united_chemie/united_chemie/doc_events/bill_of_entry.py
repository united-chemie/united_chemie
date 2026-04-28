# Copyright (c) 2023, Resilient Tech and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, today
import erpnext
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from erpnext.controllers.accounts_controller import AccountsController
from erpnext.controllers.taxes_and_totals import get_round_off_applicable_accounts

from india_compliance.gst_india.overrides.ineligible_itc import (
    update_landed_cost_voucher_for_gst_expense,
    update_regional_gl_entries,
    update_valuation_rate,
)
from india_compliance.gst_india.overrides.transaction import GSTAccounts
from india_compliance.gst_india.utils import get_gst_accounts_by_type




def validate_taxes(self):
    input_accounts = get_gst_accounts_by_type(self.company, "Input", throw=True)
    taxable_value_map = {}

    for row in self.get("items"):
        taxable_value_map[row.name] = row.taxable_value

    for tax in self.taxes:
        if not tax.tax_amount:
            continue

        if tax.account_head not in (
            input_accounts.igst_account,
            input_accounts.cess_account,
            input_accounts.cess_non_advol_account,
        ):
            frappe.throw(
                _(
                    "Row #{0}: Only Input IGST and CESS accounts are allowed in"
                    " Bill of Entry"
                ).format(tax.idx)
            )

        GSTAccounts.validate_charge_type_for_cess_non_advol_accounts(tax)
        #FinByz Changes Start
        if tax.charge_type == "Actual":

            item_wise_tax_rates = json.loads(tax.item_wise_tax_rates)
        #     if not item_wise_tax_rates:
        #         frappe.throw(
        #             _(
        #                 "Tax Row #{0}: Charge Type is set to Actual. However, this would"
        #                 " not compute item taxes, and your further reporting will be affected."
        #             ).format(tax.idx),
        #             title=_("Invalid Charge Type"),
        #         )

            # validating total tax
            total_tax = 0
            for item, rate in item_wise_tax_rates.items():
                item_taxable_value = taxable_value_map.get(item, 0)
                total_tax += item_taxable_value * rate / 100

        #     tax_difference = abs(total_tax - tax.tax_amount)

        #     if tax_difference > 1:
        #         frappe.throw(
        #             _(
        #                 "Tax Row #{0}: Charge Type is set to Actual. However, Tax Amount {1}"
        #                 " is incorrect. Try setting the Charge Type to On Net Total."
        #             ).format(row.idx, tax.tax_amount)
        #         )
        #FinByz Changes End

def set_total_taxes(self):
        total_taxes = 0

        round_off_accounts = get_round_off_applicable_accounts(self.company, [])
        for tax in self.taxes:
            if tax.charge_type == "Actual":
                tax.tax_amount = tax.tax_amount or 0
                total_taxes += tax.tax_amount
                continue

            tax.tax_amount = self.get_tax_amount(
                tax.item_wise_tax_rates, tax.charge_type
            )

            if tax.account_head in round_off_accounts:
                tax.tax_amount = round(tax.tax_amount, 0)

            total_taxes += tax.tax_amount
            tax.total = self.total_taxable_value + total_taxes

        self.total_taxes = total_taxes
