import frappe
from erpnext.assets.doctype.asset.asset import get_straight_line_or_manual_depr_amount
from erpnext.assets.doctype.asset.asset import get_shift_depr_amount
from erpnext.assets.doctype.asset.asset import get_wdv_or_dd_depr_amount

def custom_get_depreciation_amount(
	asset,
	depreciable_value,
	yearly_opening_wdv,
	fb_row,
	schedule_idx=0,
	prev_depreciation_amount=0,
	has_wdv_or_dd_non_yearly_pro_rata=False,
	number_of_pending_depreciations=0,
):
	frappe.flags.company = asset.company

	if fb_row.depreciation_method in ("Straight Line", "Manual"):
		return get_straight_line_or_manual_depr_amount(
			asset, fb_row, schedule_idx, number_of_pending_depreciations
		)
	else:
		if fb_row.shift_based and fb_row.depreciation_method == "Written Down Value":
			return get_shift_depr_amount(asset, fb_row, schedule_idx)

		return get_wdv_or_dd_depr_amount(
			asset,
			fb_row,
			depreciable_value,
			yearly_opening_wdv,
			schedule_idx,
			prev_depreciation_amount,
			has_wdv_or_dd_non_yearly_pro_rata,
		)