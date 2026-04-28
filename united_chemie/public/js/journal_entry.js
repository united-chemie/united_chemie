frappe.ui.form.on('Journal Entry', {
    refresh: function(frm) {
        set_due_date_based_on_payment_terms(frm);
    },
    validate: function(frm) {
        set_due_date_based_on_payment_terms(frm);
    },
    posting_date: function(frm) {
        set_due_date_based_on_payment_terms(frm);
    },
    accounts_add: function(frm, cdt, cdn) {
        set_due_date_based_on_payment_terms(frm);
    }
});

async function set_due_date_based_on_payment_terms(frm) {
    let posting_date = frm.doc.posting_date;
    let payment_terms = 0;

    // Log the posting_date for debugging
    // console.log(`Posting Date: ${posting_date}`);

    for (let row of frm.doc.accounts || []) {
        if (row.party_type === 'Supplier' || row.party_type === 'Customer') {
            if (row.party) {
                    let response = await frappe.db.get_value(row.party_type, row.party, 'payment_terms');
                    // response object
                    console.log(`Fetched payment_terms response for ${row.party_type} ${row.party}:`, response);

                    if (response && response.message && response.message.payment_terms) {
                        payment_terms = response.message.payment_terms;
                        console.log(`Payment Terms: ${payment_terms}`);
                        break;
                    } else {
                        console.error('Payment terms not found in the response:', response);
                    }
            }
        }
    }

    if (posting_date && payment_terms) {
        let due_date = frappe.datetime.add_days(posting_date, parseInt(payment_terms));
        // Set the due date field
        frm.set_value('due_date', due_date);
    } else {
        console.log('Posting date or payment terms are missing.');
    }

    frm.refresh_field('accounts');
}
