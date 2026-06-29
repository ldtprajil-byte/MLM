import frappe

def get_context(context):
	context.no_cache = 1

	distributor = frappe.form_dict.get("distributor")
	filter_date_from = frappe.form_dict.get("date_from")
	filter_date_to = frappe.form_dict.get("date_to")
	filter_type = frappe.form_dict.get("type")

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
	context.filter_date_from = filter_date_from or ""
	context.filter_date_to = filter_date_to or ""
	context.filter_type = filter_type if filter_type in ("Credit", "Debit") else ""

	transaction_filters = {"wallet": wallet.name}
	if context.filter_date_from and context.filter_date_to:
		transaction_filters["posting_date"] = ["between", [
			f"{context.filter_date_from} 00:00:00",
			f"{context.filter_date_to} 23:59:59",
		]]
	elif context.filter_date_from:
		transaction_filters["posting_date"] = [">=", f"{context.filter_date_from} 00:00:00"]
	elif context.filter_date_to:
		transaction_filters["posting_date"] = ["<=", f"{context.filter_date_to} 23:59:59"]
	if context.filter_type:
		transaction_filters["transaction_type"] = context.filter_type

	context.transactions = frappe.get_all("Wallet Transaction",
		filters=transaction_filters,
		fields=["posting_date", "transaction_type", "amount", "balance_before", "balance_after", "remarks"],
		order_by="posting_date desc",
		limit=50
	)
