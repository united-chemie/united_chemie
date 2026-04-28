frappe.ui.form.on('BOM', {
    onload: function(frm) {
        frm.fields_dict['additional_cost'].grid.get_field('account').get_query = function(doc, cdt, cdn) {
            return {
                filters: {
                    parent_account: `Stock Expenses - ${frm.doc.company_abbr}`, // Use the company abbreviation dynamically
                    company: frm.doc.company // Ensure accounts belong to the current company
                }
            };
        };
    },
    refresh: function(frm) {
        // Fetch the abbreviation from the Company doctype
        if (frm.doc.company) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Company",
                    filters: { name: frm.doc.company },
                    fieldname: "abbr"
                },
                callback: function(response) {
                    if (response && response.message) {
                        frm.doc.company_abbr = response.message.abbr; // Save the abbreviation for use
                    }
                }
            });
        }
    }
});
