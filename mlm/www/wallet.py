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

	wallet = frappe.db.get_value("Wallet",
		{"distributor": distributor},
		["name", "current_balance", "total_credit", "total_debit"],
		as_dict=True
	)

	if not wallet:
		context.error = "No wallet found."
		return

	context.distributor = distributor
	context.distributor_name = frappe.db.get_value("Distributor", distributor, "distributor_name")
	context.balance = wallet.current_balance or 0
	context.total_credit = wallet.total_credit or 0
	context.total_debit = wallet.total_debit or 0
	context.transactions = frappe.get_all("Wallet Transaction",
		filters={"wallet": wallet.name},
		fields=["posting_date", "transaction_type", "amount", "balance_before", "balance_after", "remarks"],
		order_by="posting_date desc",
		limit=50
	)
