// Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bulk BOM Update', {
    fetch_details: function(frm) {
        if (frm.doc.item_code || frm.doc.item_group) {
            frm.doc.bom_details = []; 

            frm.call({
                doc: frm.doc,
                method: "get_bom_details",
                args: {
                    item_code: frm.doc.item_code,
                    item_group: frm.doc.item_group,
                },
            }).then((r) => {
                if (r.message) {
                    console.log(r.message);
                    r.message.forEach((element) => {
                        var bom_entry = frm.add_child("bom_details");
                        bom_entry.bom = element.bom;
                        bom_entry.item_code = element.item_code;
                    });
                    frm.refresh_field("bom_details"); 
                }
            });
        } else {
            frappe.msgprint("Please select either Item Code or Item Group.");
        }
    },

    fetch_additional_cost: function(frm) {
        if (!frm.doc.bom_details || frm.doc.bom_details.length === 0) {
            frappe.msgprint("Please fetch BOM details first.");
            return;
        }

        let bom_name = frm.doc.bom_details[0].bom;

        if (bom_name) {
            frm.doc.additional_cost = [];

            frm.call({
                method: "united_chemie.united_chemie.doctype.bulk_bom_update.bulk_bom_update.get_bom_additional_costs",
                args: { bom_name: bom_name },
            }).then((r) => {
                if (r.message) {
                    console.log(r.message);
                    r.message.forEach((element) => {
                        let cost_entry = frm.add_child("additional_cost");
                        cost_entry.description = element.description;
                        cost_entry.account = element.account;
                        cost_entry.qty = element.qty;
                        cost_entry.uom = element.uom;
                        cost_entry.rate = element.rate;
                        cost_entry.amount = element.amount;
                    });
                    frm.refresh_field("additional_cost");
                }
				else {
					frappe.msgprint("No additional costs found for the selected BOM.");
				}
            });
        } else {
            frappe.msgprint("Please select a BOM first.");
        }
    },

    item_code: function(frm) {
        let item_code = frm.doc.item_code;

        frm.set_value('bom_details', []); 

        frm.fields_dict['bom_details'].grid.get_field('bom').get_query = function(doc, cdt, cdn) {
            return {
                filters: [
                    ['BOM', 'item', '=', item_code],   
                    ['BOM', 'is_active', '=', 1], 
                    ['BOM', 'is_default', '=', 1]
                ]
            };
        };
    },

    refresh: function(frm) {
		frm.fields_dict.additional_cost.grid.update_docfield_property("qty", "read_only", 1);
		frm.fields_dict.additional_cost.grid.update_docfield_property("uom", "read_only", 1);
        frm.fields_dict['additional_cost'].grid.refresh();
    }
});

frappe.ui.form.on("BOM Additional Cost", {
    rate: function(frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.model.set_value(d.doctype, d.name, 'amount', flt(d.qty * d.rate));
        frm.refresh_field('additional_cost');
    },
});
