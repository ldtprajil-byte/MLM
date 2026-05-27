import frappe

def get_context(context):
	context.no_cache = 1

	distributor = frappe.form_dict.get("distributor")

	if not distributor:
		context.error = "Distributor not specified."
		return

	if not frappe.db.exists("Distributor", distributor):
		context.error = "Distributor not found."
		return

	context.distributor = distributor
	context.distributor_name = frappe.db.get_value("Distributor", distributor, "distributor_name")
	context.transactions = frappe.get_all("Business Transaction",
		filters={"distributor": distributor},
		fields=["name", "posting_date", "transaction_type", "amount", "pv", "bv", "status"],
		order_by="posting_date desc",
		limit=50
	)
