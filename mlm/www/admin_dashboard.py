import json

import frappe
from frappe.utils import add_days, flt, today


def as_json(value):
	return json.dumps(value, default=str)


def date_range(days):
	return [add_days(today(), -i) for i in range(days - 1, -1, -1)]


def scalar(query, values=None):
	return flt(frappe.db.sql(query, values or ())[0][0])


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		context.error = "Please login to view the admin dashboard."
		return

	if "System Manager" not in frappe.get_roles(frappe.session.user):
		context.error = "You do not have permission to view the admin dashboard."
		return

	context.total_distributors = frappe.db.count("Distributor")
	context.active_distributors = frappe.db.count("Distributor", {"status": "Active"})
	context.inactive_distributors = frappe.db.count("Distributor", {"status": "Inactive"})
	context.blocked_distributors = frappe.db.count("Distributor", {"status": "Blocked"})

	context.total_wallet_balance = scalar("SELECT SUM(current_balance) FROM `tabWallet`")
	context.total_wallet_credit = scalar("SELECT SUM(total_credit) FROM `tabWallet`")
	context.total_wallet_debit = scalar("SELECT SUM(total_debit) FROM `tabWallet`")

	context.total_commission = scalar(
		"SELECT SUM(commission_amount) FROM `tabCommission Ledger` WHERE docstatus=1"
	)
	context.paid_commission = scalar(
		"""
		SELECT SUM(commission_amount)
		FROM `tabCommission Ledger`
		WHERE docstatus=1 AND status='Paid'
		"""
	)
	context.pending_commission = scalar(
		"""
		SELECT SUM(commission_amount)
		FROM `tabCommission Ledger`
		WHERE docstatus=1 AND status='Pending'
		"""
	)

	business_totals = frappe.db.sql(
		"""
		SELECT SUM(amount), SUM(pv), SUM(bv)
		FROM `tabBusiness Transaction`
		WHERE docstatus < 2
		"""
	)[0]
	context.total_business = flt(business_totals[0])
	context.total_pv = flt(business_totals[1])
	context.total_bv = flt(business_totals[2])

	network_totals = frappe.db.sql(
		"SELECT SUM(left_count), SUM(right_count) FROM `tabNetwork Node`"
	)[0]
	context.left_count = flt(network_totals[0])
	context.right_count = flt(network_totals[1])
	context.total_downline = context.left_count + context.right_count

	trend_days = date_range(14)
	income_values = []
	business_values = []

	for day in trend_days:
		income_values.append(
			scalar(
				"""
				SELECT SUM(commission_amount)
				FROM `tabCommission Ledger`
				WHERE DATE(creation)=%s AND docstatus=1
				""",
				(day,),
			)
		)
		business_values.append(
			scalar(
				"""
				SELECT SUM(amount)
				FROM `tabBusiness Transaction`
				WHERE DATE(posting_date)=%s AND docstatus < 2
				""",
				(day,),
			)
		)

	context.trend_labels = as_json(trend_days)
	context.income_values = as_json(income_values)
	context.business_values = as_json(business_values)

	commission_types = ["Direct", "Binary", "ROI", "Matching", "Generation"]
	commission_type_values = []
	for item in commission_types:
		commission_type_values.append(
			scalar(
				"""
				SELECT SUM(commission_amount)
				FROM `tabCommission Ledger`
				WHERE docstatus=1 AND commission_type=%s
				""",
				(item,),
			)
		)
	context.commission_type_labels = as_json(commission_types)
	context.commission_type_values = as_json(commission_type_values)

	status_rows = frappe.db.sql(
		"""
		SELECT status, COUNT(*) AS total
		FROM `tabDistributor`
		GROUP BY status
		ORDER BY COUNT(*) DESC
		""",
		as_dict=True,
	)
	context.status_labels = as_json([row.status or "Unknown" for row in status_rows])
	context.status_values = as_json([row.total for row in status_rows])

	rank_rows = frappe.db.sql(
		"""
		SELECT COALESCE(current_rank, 'No Rank') AS rank_name, COUNT(*) AS total
		FROM `tabDistributor`
		GROUP BY current_rank
		ORDER BY total DESC
		LIMIT 8
		""",
		as_dict=True,
	)
	context.rank_labels = as_json([row.rank_name for row in rank_rows])
	context.rank_values = as_json([row.total for row in rank_rows])

	context.top_earners = frappe.db.sql(
		"""
		SELECT
			cl.distributor,
			COALESCE(d.distributor_name, cl.distributor) AS distributor_name,
			SUM(cl.commission_amount) AS total_commission
		FROM `tabCommission Ledger` cl
		LEFT JOIN `tabDistributor` d ON d.name = cl.distributor
		WHERE cl.docstatus=1
		GROUP BY cl.distributor
		ORDER BY total_commission DESC
		LIMIT 8
		""",
		as_dict=True,
	)

	context.recent_transactions = frappe.get_all(
		"Business Transaction",
		fields=["name", "distributor", "posting_date", "transaction_type", "amount", "status"],
		order_by="posting_date desc, creation desc",
		limit=8,
	)

	context.recent_commissions = frappe.get_all(
		"Commission Ledger",
		filters={"docstatus": 1},
		fields=["name", "distributor", "creation", "commission_type", "commission_amount", "status"],
		order_by="creation desc",
		limit=8,
	)

	insights = []
	if context.pending_commission:
		insights.append(f"Pending commission to review: ₹{context.pending_commission}.")
	if context.blocked_distributors:
		insights.append(f"Blocked distributors need attention: {context.blocked_distributors}.")
	if sum(income_values[-7:]) > sum(income_values[:7]):
		insights.append("Commission growth is higher in the latest 7 days than the previous 7 days.")
	if context.total_wallet_balance < context.pending_commission:
		insights.append("Pending commission is higher than current wallet balance across the platform.")
	if not insights:
		insights.append("Platform metrics look steady based on the current data.")

	context.insights = insights
