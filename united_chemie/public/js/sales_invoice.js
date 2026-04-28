frappe.ui.form.on('Sales Invoice', {
    total_commission(frm) {
        set_commission_in_company_currency(frm);
    },
    conversion_rate(frm) {
        set_commission_in_company_currency(frm);
    },
    refresh(frm) {
        set_commission_in_company_currency(frm);
    }
});

function set_commission_in_company_currency(frm) {
    if (frm.doc.total_commission && frm.doc.conversion_rate) {
        frm.set_value(
            'commission_in_company_currency',
            frm.doc.total_commission * frm.doc.conversion_rate
        );
    } else {
        frm.set_value('commission_in_company_currency', 0);
    }
}
