import json
from collections import defaultdict

import frappe
from frappe import _, bold
from frappe.model import delete_doc
from frappe.utils import cint, flt
from erpnext.controllers.accounts_controller import get_taxes_and_charges

from india_compliance.gst_india.constants import (
    GST_TAX_TYPES,
    SALES_DOCTYPES,
    STATE_NUMBERS,
)
from india_compliance.gst_india.constants.custom_fields import E_WAYBILL_INV_FIELDS
from india_compliance.gst_india.overrides.transaction import ItemGSTDetails
from india_compliance.gst_india.utils import (
    get_all_gst_accounts,
    get_gst_accounts_by_tax_type,
    get_gst_accounts_by_type,
    get_hsn_settings,
    get_place_of_supply,
    get_place_of_supply_options,
    is_overseas_doc,
    join_list_with_custom_separators,
    validate_gst_category,
    validate_gstin,
)
from india_compliance.income_tax_india.overrides.tax_withholding_category import (
    get_tax_withholding_accounts,
)
from india_compliance.gst_india.overrides.transaction import (validate_place_of_supply, ignore_gst_validations, validate_company_address_field, validate_mandatory_fields, 
validate_overseas_gst_category,update_taxable_values,set_reverse_charge_as_per_gst_settings,validate_ecommerce_gstin,validate_hsn_codes,validate_gst_transporter_id, validate_reverse_charge_transaction, validate_gstin_status)

DOCTYPES_WITH_GST_DETAIL = {
    "Supplier Quotation",
    "Purchase Order",
    "Purchase Receipt",
    "Quotation",
    "Sales Order",
    "Delivery Note",
    "Sales Invoice",
    "POS Invoice",
}
def validate_gst_accounts(doc, is_sales_transaction=False):
    """
    Validate GST accounts
    - Only Valid Accounts should be allowed
    - No GST account should be specified for transactions where Company GSTIN = Party GSTIN
    - If export is made without GST, then no GST account should be specified
    - SEZ / Inter-State supplies should not have CGST or SGST account
    - Intra-State supplies should not have IGST account
    """
    if not doc.taxes:
        return

    if not (
        rows_to_validate := [
            row
            for row in doc.taxes
            if row.tax_amount and row.account_head in get_all_gst_accounts(doc.company)
        ]
    ):
        return

    # Helper functions

    def _get_matched_idx(rows_to_search, account_head_list):
        return next(
            (
                row.idx
                for row in rows_to_search
                if row.account_head in account_head_list
            ),
            None,
        )

    def _throw(message, title=None):
        frappe.throw(message, title=title or _("Invalid GST Account"))

    all_valid_accounts, intra_state_accounts, inter_state_accounts = get_valid_accounts(
        doc.company,
        for_sales=is_sales_transaction,
        for_purchase=not is_sales_transaction,
    )
    cess_non_advol_accounts = get_gst_accounts_by_tax_type(
        doc.company, "cess_non_advol"
    )

    # Company GSTIN = Party GSTIN
    party_gstin = (
        doc.billing_address_gstin if is_sales_transaction else doc.supplier_gstin
    )
    if (
        party_gstin
        and doc.company_gstin == party_gstin
        and (idx := _get_matched_idx(rows_to_validate, all_valid_accounts))
    ):
        _throw(
            _(
                "Cannot charge GST in Row #{0} since Company GSTIN and Party GSTIN are"
                " same"
            ).format(idx)
        )

    # Sales / Purchase Validations
    if is_sales_transaction:
        if is_export_without_payment_of_gst(doc) and (
            idx := _get_matched_idx(rows_to_validate, all_valid_accounts)
        ):
            _throw(
                _(
                    "Cannot charge GST in Row #{0} since export is without"
                    " payment of GST"
                ).format(idx)
            )

        if doc.get("is_reverse_charge") and (
            idx := _get_matched_idx(rows_to_validate, all_valid_accounts)
        ):
            _throw(
                _(
                    "Cannot charge GST in Row #{0} since supply is under reverse charge"
                ).format(idx)
            )

    elif doc.gst_category == "Registered Composition" and (
        idx := _get_matched_idx(rows_to_validate, all_valid_accounts)
    ):
        _throw(
            _(
                "Cannot claim Input GST in Row #{0} since purchase is being made from a"
                " dealer registered under Composition Scheme"
            ).format(idx)
        )

    elif not doc.is_reverse_charge:
        if idx := _get_matched_idx(
            rows_to_validate,
            get_gst_accounts_by_type(doc.company, "Reverse Charge").values(),
        ):
            _throw(
                _(
                    "Cannot use Reverse Charge Account in Row #{0} since purchase is"
                    " without Reverse Charge"
                ).format(idx)
            )

        if not doc.supplier_gstin and (
            idx := _get_matched_idx(rows_to_validate, all_valid_accounts)
        ):
            _throw(
                _(
                    "Cannot charge GST in Row #{0} since purchase is from a Supplier"
                    " without GSTIN"
                ).format(idx)
            )

    is_inter_state = is_inter_state_supply(doc)
    previous_row_references = set()

    for row in rows_to_validate:
        account_head = row.account_head

        if row.charge_type == "Actual":
            item_tax_detail = frappe.parse_json(row.get("item_wise_tax_detail") or {})
            for tax_rate, tax_amount in item_tax_detail.values():
                if tax_amount and not tax_rate:
                    #Finbyz Changes start
                    if is_sales_transaction:
                    #finbyz changes End
                        _throw(
                            _(
                                "Tax Row #{0}: Charge Type is set to Actual. However, this would"
                                " not compute item taxes, and your further reporting will be affected."
                            ).format(row.idx),
                            title=_("Invalid Charge Type"),
                        )

        if account_head not in all_valid_accounts:
            _throw(
                _("{0} is not a valid GST account for this transaction").format(
                    bold(account_head)
                ),
            )

        # Inter State supplies should not have CGST or SGST account
        if is_inter_state:
            if account_head in intra_state_accounts:
                _throw(
                    _(
                        "Row #{0}: Cannot charge CGST/SGST for inter-state supplies"
                    ).format(row.idx),
                )

        # Intra State supplies should not have IGST account
        elif account_head in inter_state_accounts:
            _throw(
                _("Row #{0}: Cannot charge IGST for intra-state supplies").format(
                    row.idx
                ),
            )

        if row.charge_type == "On Previous Row Amount":
            _throw(
                _(
                    "Row #{0}: Charge Type cannot be <strong>On Previous Row"
                    " Amount</strong> for a GST Account"
                ).format(row.idx),
                title=_("Invalid Charge Type"),
            )

        if row.charge_type == "On Previous Row Total":
            previous_row_references.add(row.row_id)

        if (
            row.charge_type == "On Item Quantity"
            and account_head not in cess_non_advol_accounts
        ):
            _throw(
                _(
                    "Row #{0}: Charge Type cannot be <strong>On Item Quantity</strong>"
                    " as it is not a Cess Non Advol Account"
                ).format(row.idx),
                title=_("Invalid Charge Type"),
            )

        if (
            row.charge_type != "On Item Quantity"
            and account_head in cess_non_advol_accounts
        ):
            _throw(
                _(
                    "Row #{0}: Charge Type must be <strong>On Item Quantity</strong>"
                    " as it is a Cess Non Advol Account"
                ).format(row.idx),
                title=_("Invalid Charge Type"),
            )

    used_accounts = set(row.account_head for row in rows_to_validate)
    if not is_inter_state:
        if used_accounts and not set(intra_state_accounts[:2]).issubset(used_accounts):
            _throw(
                _(
                    "Cannot use only one of CGST or SGST account for intra-state"
                    " supplies"
                ),
                title=_("Invalid GST Accounts"),
            )

    if len(previous_row_references) > 1:
        _throw(
            _(
                "Only one row can be selected as a Reference Row for GST Accounts with"
                " Charge Type <strong>On Previous Row Total</strong>"
            ),
            title=_("Invalid Reference Row"),
        )

    for row in doc.get("items") or []:
        if not row.item_tax_template:
            continue

        for account in used_accounts:
            if account in row.item_tax_rate:
                continue

            frappe.msgprint(
                _(
                    "Item Row #{0}: GST Account {1} is missing in Item Tax Template {2}"
                ).format(row.idx, bold(account), bold(row.item_tax_template)),
                title=_("Invalid Item Tax Template"),
                indicator="orange",
            )

    return all_valid_accounts
def custom_validate_item_wise_tax_detail(doc):
    if doc.doctype not in DOCTYPES_WITH_GST_DETAIL:
        return

    item_taxable_values = defaultdict(float)
    item_qty_map = defaultdict(float)

    for row in doc.items:
        item_key = row.item_code or row.item_name
        item_taxable_values[item_key] += row.taxable_value
        item_qty_map[item_key] += row.qty

    for row in doc.taxes:
        if not row.gst_tax_type:
            continue

        if row.charge_type != "Actual":
            continue

        item_wise_tax_detail = frappe.parse_json(row.item_wise_tax_detail or "{}")

        for item_name, (tax_rate, tax_amount) in item_wise_tax_detail.items():
            if tax_amount and not tax_rate:
                pass
                # frappe.throw(
                #     _(
                #         "Tax Row #{0}: Charge Type is set to Actual. However, this would"
                #         " not compute item taxes, and your further reporting will be affected."
                #     ).format(row.idx),
                #     title=_("Invalid Charge Type"),
                # )

            # Sales Invoice is created with manual tax amount. So, when a sales return is created,
            # the tax amount is not recalculated, causing the issue.

            is_cess_non_advol = "cess_non_advol" in row.gst_tax_type
            multiplier = (
                item_qty_map.get(item_name, 0)
                if is_cess_non_advol
                else item_taxable_values.get(item_name, 0) / 100
            )
            tax_difference = abs(multiplier * tax_rate - tax_amount)

            if tax_difference > 1:
                correct_charge_type = (
                    "On Item Quantity" if is_cess_non_advol else "On Net Total"
                )

                # frappe.throw(
                #     _(
                #         "Tax Row #{0}: Charge Type is set to Actual. However, Tax Amount {1} as computed for Item {2}"
                #         " is incorrect. Try setting the Charge Type to {3}"
                #     ).format(row.idx, tax_amount, bold(item_name), correct_charge_type)
                # )   

def get_(self, docs, doctype, company):
    """
    Return Item GST Details for a list of documents
    """
    self.set_gst_accounts_and_item_defaults(doctype, company)
    self.set_tax_amount_precisions(doctype)

    response = frappe._dict()

    if not self.gst_account_map:
        return response

    for doc in docs:
        self.doc = doc
        if not doc.get("items") or not doc.get("taxes"):
            continue

        self.set_item_wise_tax_details()

        max_idx = 0
        if idxs := [item.idx for item in self.doc.get("items")]:
            max_idx = max(idxs)

        for item in doc.get("items"):
            response[item.name] = self.get_item_tax_detail(item, max_idx)

    return response

def set_item_wise_tax_details_(self):
    """
    Item Tax Details complied
    Example:
    {
        "Item Code 1": {
            "count": 2,
            "cgst_rate": 9,
            "cgst_amount": 18,
            "sgst_rate": 9,
            "sgst_amount": 18,
            ...
        },
        ...
    }

    Possible Exceptions Handled:
    - There could be more than one row for same account
    - Item count added to handle rounding errors
    """

    tax_details = frappe._dict()

    for row in self.doc.get("items"):
        key = row.item_code or row.item_name
        if key not in tax_details:
            tax_details[key] = self.item_defaults.copy()
        tax_details[key]["count"] += 1

    for row in self.doc.taxes:
        if (
            not row.base_tax_amount_after_discount_amount
            or row.gst_tax_type not in GST_TAX_TYPES
            or not row.item_wise_tax_detail
        ):
            continue

        tax = row.gst_tax_type
        tax_rate_field = f"{tax}_rate"
        tax_amount_field = f"{tax}_amount"

        old = json.loads(row.item_wise_tax_detail)

        tax_difference = row.base_tax_amount_after_discount_amount
        base_tax_amount = flt(row.base_tax_amount, 2)

        # update item taxes
        for idx, item_name in enumerate(old):
            if item_name not in tax_details:
                # Do not compute if Item is not present in Item table
                # There can be difference in Item Table and Item Wise Tax Details
                continue

            item_taxes = tax_details[item_name]
            tax_rate, tax_amount = old[item_name]

            tax_amount = flt(tax_amount, 2)
            base_tax_amount = flt(base_tax_amount - tax_amount, 2)

            tax_difference -= tax_amount

            # cases when charge type == "Actual"
            if tax_amount and not tax_rate:
                continue

            item_taxes[tax_rate_field] = tax_rate
            item_taxes[tax_amount_field] += tax_amount
        
        item_taxes[tax_amount_field] += base_tax_amount

        # Floating point errors
        tax_difference = flt(tax_difference, 5)

        # Handle rounding errors
        if tax_difference:
            item_taxes[tax_amount_field] += tax_difference

    self.item_tax_details = tax_details

def get_item_tax_detail_(self, item, max_idx=0):
    """
    - get item_tax_detail as it is if
        - only one row exists for same item
        - it is the last item

    - If count is greater than 1,
        - Manually calculate tax_amount for item
        - Reduce item_tax_detail with
            - tax_amount
            - count
    """
    item_key = self.get_item_key(item)

    item_tax_detail = self.item_tax_details.get(item_key)
    if not item_tax_detail:
        return {}

    #FINBYZ CHAGE START TO MAINTAIN PRECISION IN SALES INVOICE TAX CALCULATION: COMMENTED BELOW LINE

    # if item_tax_detail.count == 1:
    #     return item_tax_detail

    #FINBYZ CHAGES END TO MAINTAIN PRECISION IN SALES INVOICE TAX CALCULATION

    item_tax_detail["count"] -= 1

    # Handle rounding errors
    response = item_tax_detail.copy()
    for tax in GST_TAX_TYPES:
        if (tax_rate := item_tax_detail[f"{tax}_rate"]) == 0:
            continue

        tax_amount_field = f"{tax}_amount"
        precision = self.precision.get(tax_amount_field)

        multiplier = (
            item.qty if tax == "cess_non_advol" else item.taxable_value / 100
        )
        tax_amount = flt(tax_rate * multiplier, precision)

        if item.idx == max_idx:
            tax_amount = item_tax_detail[tax_amount_field]

        item_tax_detail[tax_amount_field] -= tax_amount

        response.update({tax_amount_field: tax_amount})

    return response

def update_item_tax_details_(self):
    max_idx = 0
    if idxs := [item.idx for item in self.doc.get("items")]:
        max_idx = max(idxs)
    
    for item in self.doc.get("items"):
        item.update(self.get_item_tax_detail(item, max_idx))
