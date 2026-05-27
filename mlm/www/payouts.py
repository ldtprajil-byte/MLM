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
	context.payouts = frappe.get_all("Payout Request",
		filters={"distributor": distributor},
		fields=["name", "request_date", "request_amount", "charges", "net_amount", "payout_method", "status", "approved_on"],
		order_by="request_date desc",
		limit=50
	)
