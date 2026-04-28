# my_custom_app/overrides/exchange_rate_revaluation.py

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form
from erpnext.accounts.utils import get_balance_on
import erpnext

from erpnext.accounts.doctype.exchange_rate_revaluation.exchange_rate_revaluation import ExchangeRateRevaluation

class CustomExchangeRateRevaluation(ExchangeRateRevaluation):
    @frappe.whitelist()
    def make_jv_entries(self):
        zero_balance_jv = self.make_jv_for_zero_balance()
        if zero_balance_jv:
            frappe.msgprint(
                f"Zero Balance Journal: {get_link_to_form('Journal Entry', zero_balance_jv.name)}"
            )

        revaluation_jv = self.make_jv_for_revaluation()
        if revaluation_jv:
            frappe.msgprint(f"Revaluation Journal: {get_link_to_form('Journal Entry', revaluation_jv.name)}")

        return {
            "revaluation_jv": revaluation_jv.name if revaluation_jv else None,
            "zero_balance_jv": zero_balance_jv.name if zero_balance_jv else None,
        }

    def make_jv_for_zero_balance(self):
        if self.gain_loss_booked == 0:
            return

        accounts = [x for x in self.accounts if x.zero_balance]

        if not accounts:
            return

        unrealized_exchange_gain_loss_account = self.get_for_unrealized_gain_loss_account()

        journal_entry = frappe.new_doc("Journal Entry")
        journal_entry.voucher_type = "Exchange Gain Or Loss"
        journal_entry.company = self.company
        journal_entry.posting_date = self.posting_date
        journal_entry.multi_currency = 1

        journal_entry_accounts = []
        for d in accounts:
            journal_account = frappe._dict(
                {
                    "account": d.get("account"),
                    "party_type": d.get("party_type"),
                    "party": d.get("party"),
                    "account_currency": d.get("account_currency"),
                    "balance": flt(d.get("balance_in_account_currency"), d.precision("balance_in_account_currency")),
                    "exchange_rate": 0,
                    "cost_center": erpnext.get_default_cost_center(self.company),
                    # "reference_type": "Exchange Rate Revaluation",
                    # "reference_name": self.name,
                }
            )

            # Account Currency has balance
            if d.get("balance_in_account_currency") and not d.get("new_balance_in_account_currency"):
                dr_or_cr = (
                    "credit_in_account_currency"
                    if d.get("balance_in_account_currency") > 0
                    else "debit_in_account_currency"
                )
                reverse_dr_or_cr = (
                    "debit_in_account_currency"
                    if dr_or_cr == "credit_in_account_currency"
                    else "credit_in_account_currency"
                )
                journal_account.update(
                    {
                        dr_or_cr: flt(abs(d.get("balance_in_account_currency")), d.precision("balance_in_account_currency")),
                        reverse_dr_or_cr: 0,
                        "debit": 0,
                        "credit": 0,
                    }
                )

                journal_entry_accounts.append(journal_account)

                journal_entry_accounts.append(
                    {
                        "account": unrealized_exchange_gain_loss_account,
                        "balance": get_balance_on(unrealized_exchange_gain_loss_account),
                        "debit": 0,
                        "credit": 0,
                        "debit_in_account_currency": abs(d.gain_loss) if d.gain_loss < 0 else 0,
                        "credit_in_account_currency": abs(d.gain_loss) if d.gain_loss > 0 else 0,
                        "cost_center": erpnext.get_default_cost_center(self.company),
                        "exchange_rate": 1,
                        # "reference_type": "Exchange Rate Revaluation",
                        # "reference_name": self.name,
                    }
                )

            elif d.get("balance_in_base_currency") and not d.get("new_balance_in_base_currency"):
                dr_or_cr = "credit" if d.get("balance_in_base_currency") > 0 else "debit"
                reverse_dr_or_cr = "debit" if dr_or_cr == "credit" else "credit"
                journal_account.update(
                    {
                        dr_or_cr: flt(abs(d.get("balance_in_base_currency")), d.precision("balance_in_base_currency")),
                        reverse_dr_or_cr: 0,
                        "debit_in_account_currency": 0,
                        "credit_in_account_currency": 0,
                    }
                )

                journal_entry_accounts.append(journal_account)

                journal_entry_accounts.append(
                    {
                        "account": unrealized_exchange_gain_loss_account,
                        "balance": get_balance_on(unrealized_exchange_gain_loss_account),
                        "debit": abs(d.gain_loss) if d.gain_loss < 0 else 0,
                        "credit": abs(d.gain_loss) if d.gain_loss > 0 else 0,
                        "debit_in_account_currency": 0,
                        "credit_in_account_currency": 0,
                        "cost_center": erpnext.get_default_cost_center(self.company),
                        "exchange_rate": 1,
                        # "reference_type": "Exchange Rate Revaluation",
                        # "reference_name": self.name,
                    }
                )

        journal_entry.set("accounts", journal_entry_accounts)
        journal_entry.set_total_debit_credit()
        journal_entry.save()
        return journal_entry

    def make_jv_for_revaluation(self):
        if self.gain_loss_unbooked == 0:
            return

        accounts = [x for x in self.accounts if not x.zero_balance]
        if not accounts:
            return

        unrealized_exchange_gain_loss_account = self.get_for_unrealized_gain_loss_account()

        journal_entry = frappe.new_doc("Journal Entry")
        journal_entry.voucher_type = "Exchange Rate Revaluation"
        journal_entry.company = self.company
        journal_entry.posting_date = self.posting_date
        journal_entry.multi_currency = 1

        journal_entry_accounts = []
        for d in accounts:
            if not flt(d.get("balance_in_account_currency"), d.precision("balance_in_account_currency")):
                continue

            dr_or_cr = (
                "debit_in_account_currency"
                if d.get("balance_in_account_currency") > 0
                else "credit_in_account_currency"
            )

            reverse_dr_or_cr = (
                "debit_in_account_currency"
                if dr_or_cr == "credit_in_account_currency"
                else "credit_in_account_currency"
            )

            journal_entry_accounts.append(
                {
                    "account": d.get("account"),
                    "party_type": d.get("party_type"),
                    "party": d.get("party"),
                    "account_currency": d.get("account_currency"),
                    "balance": flt(d.get("balance_in_account_currency"), d.precision("balance_in_account_currency")),
                    dr_or_cr: flt(abs(d.get("balance_in_account_currency")), d.precision("balance_in_account_currency")),
                    "cost_center": erpnext.get_default_cost_center(self.company),
                    "exchange_rate": flt(d.get("new_exchange_rate"), d.precision("new_exchange_rate")),
                }
            )

            reference_fields = {}
            # if d.get("party_type") == "Customer" and dr_or_cr == "debit_in_account_currency":
            #     reference_fields = {"reference_type": "Exchange Rate Revaluation", "reference_name": self.name}
            # elif d.get("party_type") == "Supplier" and dr_or_cr == "credit_in_account_currency":
            #     reference_fields = {"reference_type": "Exchange Rate Revaluation", "reference_name": self.name}

            journal_entry_accounts.append(
                {
                    "account": d.get("account"),
                    "party_type": d.get("party_type"),
                    "party": d.get("party"),
                    "account_currency": d.get("account_currency"),
                    "balance": flt(d.get("balance_in_account_currency"), d.precision("balance_in_account_currency")),
                    reverse_dr_or_cr: flt(abs(d.get("balance_in_account_currency")), d.precision("balance_in_account_currency")),
                    "cost_center": erpnext.get_default_cost_center(self.company),
                    "exchange_rate": flt(d.get("current_exchange_rate"), d.precision("current_exchange_rate")),
                    **reference_fields,
                }
            )

        journal_entry.set("accounts", journal_entry_accounts)
        journal_entry.set_amounts_in_company_currency()
        journal_entry.set_total_debit_credit()

        self.gain_loss_unbooked += journal_entry.difference - self.gain_loss_unbooked
        journal_entry.append(
            "accounts",
            {
                "account": unrealized_exchange_gain_loss_account,
                "balance": get_balance_on(unrealized_exchange_gain_loss_account),
                "debit_in_account_currency": abs(self.gain_loss_unbooked) if self.gain_loss_unbooked < 0 else 0,
                "credit_in_account_currency": self.gain_loss_unbooked if self.gain_loss_unbooked > 0 else 0,
                "cost_center": erpnext.get_default_cost_center(self.company),
                "exchange_rate": 1,
            },
        )

        journal_entry.set_amounts_in_company_currency()
        journal_entry.set_total_debit_credit()
        journal_entry.save()
        return journal_entry
