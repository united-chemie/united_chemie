# Copyright (c) 2024, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {"label": "INVOICE NUMBER", "fieldname": "invoice_no", "fieldtype": "Link", "options": "Sales Invoice", "width": 120},
        {"label": "SALES ORDER NUMBER", "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": "INVOICE DATE", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "CONSIGNEE NAME", "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
        {"label": "PURCHASE ORDER NUMBER", "fieldname": "po_no", "fieldtype": "Data", "width": 150},
        {"label": "PO DATE", "fieldname": "po_date", "fieldtype": "Date", "width": 120},
        {"label": "CURRENCY", "fieldname": "currency", "fieldtype": "Data", "width": 100},
        {"label": "ITEM NAME", "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": "LOT NO", "fieldname": "lot_no", "fieldtype": "Data", "width": 100},
        {"label": "QUANTITY-KGS", "fieldname": "qty", "fieldtype": "Float", "width": 100},
        {"label": "RATE/KG", "fieldname": "rate", "width": 120},
        {"label": "Total Invoice Amount/ Net Total", "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 120},
       	{"label": "EXCHANGE RATE", "fieldname": "conversion_rate", "width": 120},
        {"label": "SHIPPING BILL NO.", "fieldname": "shipping_bill_number", "fieldtype": "Data", "width": 120},
        {"label": "SHIPPING BILL DATE", "fieldname": "shipping_bill_date", "fieldtype": "Date", "width": 120},
        {"label": "PORT CODE", "fieldname": "port_code", "fieldtype": "Data", "width": 120},
        {"label": "FREIGHT(FC)","fieldname": "freight", "width": 120},
        {"label": "INSURANCE(FC)","fieldname": "insurance", "width": 120},
        {"label": "FOB(FC)","fieldname": "base_fob_value", "width": 120},
        {"label":"COMMISSION","fieldname":"commission_amount","width":120},
        {"label":"DBK AMOUNT","fieldname":"total_duty_drawback", "width":120},
        {"label":"RODTEP AMOUNT","fieldname":"total_meis", "width":120},
        {"label":"INSURANCE POLICY NUMBER","fieldname":"insurance_policy_number", "width":120},
        {"label":"INSURANCE PREMIUM AMOUNT WITH GST","fieldname":"insurance_premium_amount", "width":120},
        {"label":"DRAFT BL APPROVED DATE","fieldname":"etd_destination_date",  "fieldtype": "Date", "width":120},
        {"label":"B/L NUMBER","fieldname":"bl_no", "width":120},
        {"label":"B/L DATE","fieldname":"bl_date",  "fieldtype": "Date", "width":120},
        {"label":"DUE DATE","fieldname":"due_date", "fieldtype":"Date", "width":120},
        {"label":"FOB VALUE AS PER BRC", "fieldname":"fob_value_as_per_brc" ,"fieldtype":"Data","width":120},
        {"label":"BANK REF.NO.","fieldname":"bank_reference_number", "width":120},
        {"label":"RECEIPT DATE(BRC)","fieldname":"payment_date", "fieldtype":"Date", "width":120},	
        {"label": "RECEIVED AMOUNT(payment)", "fieldname": "paid_amount","width": 120},
        {"label": "IRM NUMBER", "fieldname": "irm_number","width": 100},
        {"label": "BRC NUMBER", "fieldname": "brc_number", "width": 100},
        {"label": "BRC DATE", "fieldname": "brc_date", "fieldtype": "Date", "width": 100},
        {"label": "EGM NUMBER", "fieldname": "egm_number", "width": 100},
        {"label": "EGM DATE", "fieldname": "egm_date", "fieldtype": "Date", "width": 100},
        {"label": "INVOICE VALUE-Rs.", "fieldname": "base_total", "width": 120},
        {"label": "FOB VALUE IN -Rs.", "fieldname": "total_fob_value", "width": 120},
        {"label": "FREIGHT IN -Rs.", "fieldname": "base_freight", "width": 120},
        {"label": "INSURANCE IN -Rs.", "fieldname": "base_insurance", "width": 120},
        {"label": "PORT OF LOADING", "fieldname": "port_of_loading", "width": 120},
        {"label": "PORT OF DISCHARGE", "fieldname": "port_of_discharge", "width": 120},
        {"label": "COUNTRY OF DESTINATION", "fieldname": "country_of_destination", "width": 120},
		{"label": "PSS SEND DT", "fieldname": "pss_sent_dt","fieldtype":"Date","width": 120},
        {"label": "PSS APPROVAL DATE", "fieldname": "pss_approval_date", "fieldtype": "Date", "width": 120},
        {"label": "ETD FACTORY", "fieldname": "etd_factory_date", "fieldtype": "Date", "width": 120},
        {"label": "ETD PORT", "fieldname": "etd_port_date", "fieldtype": "Date", "width": 120},
        {"label": "REMARKS", "fieldname": "remarks", "width": 120},
        {"label": "CONSIGNEE ORDER NO.", "fieldname": "consignee_order_no", "width": 120},
        {"label": "CONSIGNEE ORDER DT.", "fieldname": "consignee_order_date", "fieldtype": "Date", "width": 120}
    ]


def get_data(filters):
    conditions = ["si.docstatus = 1"]

    if filters.get("from_date"):
        conditions.append("si.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("si.posting_date <= %(to_date)s")
    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
    if filters.get("company"):
        conditions.append("si.company = %(company)s")
    if filters.get("invoice_no"):
        conditions.append("si.name LIKE %(invoice_no)s")
    if filters.get("currency"):
        conditions.append("si.currency = %(currency)s")

    conditions_sql = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            si.name AS invoice_no,si.posting_date,si.customer_name,si.currency,si.total,si.po_no,si.lot_no,si.conversion_rate,si.shipping_bill_number,
            si.shipping_bill_date,si.port_code,si.due_date,si.bank_reference_number,ROUND(si.freight,2) AS freight,ROUND(si.insurance,2) AS insurance,
            ROUND(si.base_fob_value,2) AS base_fob_value,ROUND(si.commission_amount,2) AS commission_amount,ROUND(si.total_duty_drawback,2) AS total_duty_drawback,
            ROUND(si.total_meis,2) AS total_meis,si.insurance_policy_number,ROUND(si.insurance_premium_amount,2) AS insurance_premium_amount,si.etd_destination_date,
            si.bl_no,si.bl_date,si.egm_number,si.egm_date,si.pss_sent_dt,si.base_total,si.port_of_loading,si.port_of_discharge,si.port_of_loading,
            si.country_of_destination,si.base_freight,si.base_insurance,si.total_fob_value,si.po_date,si.po_setteled_against_inv_no,si.pss_approval_date,si.etd_factory_date,si.etd_port_date,si.remarks,
            sii.item_name,sii.sales_order,sii.qty,ROUND(sii.rate,4) AS rate,sii.amount,
            brc.brc_number,brc.brc_date,brcp.payment_date,ROUND(brcp.paid_amount,2) AS paid_amount,brc.irm_number,
            so.consignee_order_no,so.consignee_order_date,(ROUND((si.freight - si.insurance) * si.conversion_rate, 2)) AS fob_value_as_per_brc
        FROM
            `tabSales Invoice` si
        INNER JOIN
            `tabSales Invoice Item` sii ON si.name = sii.parent
        LEFT JOIN
            `tabBRC Management` brc ON si.name = brc.invoice_no
        LEFT JOIN
            `tabBRC Payment` brcp ON brc.name = brcp.parent 
        LEFT JOIN
            `tabSales Order` so ON sii.sales_order = so.name
        WHERE
            {conditions_sql}
 
    """

    data = frappe.db.sql(query, filters, as_dict=True)
    return data
