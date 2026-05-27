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

	commissions = frappe.get_all("Commission Ledger",
		filters={"distributor": distributor},
		fields=["name", "creation", "commission_type", "commission_amount", "commission_percent", "source_distributor", "source_transaction", "status"],
		order_by="creation desc",
		limit=50
	)

	# Replace IDs with names
	for c in commissions:
		if c.source_distributor:
			c.source_distributor_name = frappe.db.get_value(
				"Distributor", c.source_distributor, "distributor_name"
			) or c.source_distributor
		else:
			c.source_distributor_name = "-"

	context.commissions = commissions
	context.total_commission = sum(c.commission_amount or 0 for c in commissions)
	context.direct_total = sum(c.commission_amount or 0 for c in commissions if c.commission_type == "Direct")
	context.binary_total = sum(c.commission_amount or 0 for c in commissions if c.commission_type == "Binary")
