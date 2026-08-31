frappe.ui.form.on("Production Plan Item", {
    item_code: function(frm, cdt, cdn) {
        set_actual_stock(frm, locals[cdt][cdn]);
    },

    warehouse: function(frm, cdt, cdn) {
        set_actual_stock(frm, locals[cdt][cdn]);
    }
});


function set_actual_stock(frm, row) {

    if (!row.item_code || !row.warehouse) {
        frappe.model.set_value(
            row.doctype,
            row.name,
            "actual_stock",
            0
        );
        return;
    }

    frappe.db.get_value(
        "Bin",
        {
            item_code: row.item_code,
            warehouse: row.warehouse
        },
        "actual_qty"
    ).then(r => {

        let actual_qty = 0;

        if (r.message) {
            actual_qty = r.message.actual_qty || 0;
        }

        frappe.model.set_value(
            row.doctype,
            row.name,
            "actual_qty",
            actual_qty
        );
    });
}