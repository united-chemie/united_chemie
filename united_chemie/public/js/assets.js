frappe.ui.form.on('Asset Finance Book', {
    shift_based: function(frm,cdt,cdn){
		const row = locals[cdt][cdn];
		frm.events.set_depreciation_rate(frm, row);
		frm.events.make_schedules_editable(frm);
	},
})