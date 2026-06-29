import json

import frappe
from frappe.utils import add_days, flt, today


def as_json(value):
	return json.dumps(value, default=str)


def date_range(days):
	return [add_days(today(), -i) for i in range(days - 1, -1, -1)]


def get_context(context):
	context.no_cache = 1

	distributor = frappe.form_dict.get("distributor")

	if not distributor:
		context.error = "Distributor not specified."
		return

	if not frappe.db.exists("Distributor", distributor):
		context.error = "Distributor not found."
		return

	dist = frappe.get_doc("Distributor", distributor)

	context.distributor = distributor
	context.distributor_name = dist.distributor_name
	context.current_rank = dist.current_rank or "Starter"
	context.status = dist.status
	context.join_date = dist.join_date
	context.sponsor_name = dist.sponsor_name or dist.sponsor or "-"
	context.total_investment = flt(dist.total_investment)
	context.active_investment = flt(dist.active_investment)

	wallet = frappe.db.get_value(
		"Wallet",
		{"distributor": distributor},
		["name", "current_balance", "total_credit", "total_debit"],
		as_dict=True,
	) or {}

	wallet_name = wallet.get("name")
	balance = flt(wallet.get("current_balance"))
	total_credit = flt(wallet.get("total_credit"))
	total_debit = flt(wallet.get("total_debit"))

	context.balance = balance
	context.total_credit = total_credit
	context.total_debit = total_debit

	commissions = frappe.get_all(
		"Commission Ledger",
		filters={"distributor": distributor, "docstatus": 1},
		fields=["commission_amount", "commission_type", "status", "creation", "source_distributor"],
		order_by="creation asc",
	)

	total_commission = sum(flt(c.commission_amount) for c in commissions)
	context.total_commission = total_commission
	context.direct_commission = sum(
		flt(c.commission_amount) for c in commissions if c.commission_type == "Direct"
	)
	context.binary_commission = sum(
		flt(c.commission_amount) for c in commissions if c.commission_type == "Binary"
	)
	context.pending_commission = sum(
		flt(c.commission_amount) for c in commissions if c.status == "Pending"
	)
	context.paid_commission = sum(
		flt(c.commission_amount) for c in commissions if c.status == "Paid"
	)

	node = frappe.db.get_value(
		"Network Node",
		{"distributor": distributor},
		["left_count", "right_count"],
		as_dict=True,
	) or {}

	left = flt(node.get("left_count"))
	right = flt(node.get("right_count"))
	total_downline = left + right
	weak_leg = min(left, right)
	strong_leg = max(left, right)
	balance_score = round((weak_leg / strong_leg) * 100, 1) if strong_leg else 0

	context.left_count = left
	context.right_count = right
	context.total_downline = total_downline
	context.balance_score = balance_score
	context.weak_leg = "Left" if left <= right else "Right"

	recent_transactions = frappe.get_all(
		"Business Transaction",
		filters={"distributor": distributor},
		fields=["name", "posting_date", "transaction_type", "amount", "pv", "bv", "status"],
		order_by="posting_date desc, creation desc",
		limit=8,
	)
	context.recent_transactions = recent_transactions

	recent_commissions = frappe.get_all(
		"Commission Ledger",
		filters={"distributor": distributor, "docstatus": 1},
		fields=["name", "creation", "commission_type", "commission_amount", "status"],
		order_by="creation desc",
		limit=6,
	)
	context.recent_commissions = recent_commissions

	# Income trend: last 14 days
	trend_days = date_range(14)
	income_values = []
	for day in trend_days:
		total = frappe.db.sql(
			"""
			SELECT SUM(commission_amount)
			FROM `tabCommission Ledger`
			WHERE distributor=%s
				AND DATE(creation)=%s
				AND docstatus=1
			""",
			(distributor, day),
		)[0][0] or 0
		income_values.append(flt(total))

	context.last_7_days_income = sum(income_values[-7:])
	context.last_14_days_income = sum(income_values)
	context.income_chart_labels = as_json(trend_days)
	context.income_chart_values = as_json(income_values)

	# Business trend: amount, PV and BV for last 14 days
	amount_values = []
	pv_values = []
	bv_values = []
	for day in trend_days:
		row = frappe.db.sql(
			"""
			SELECT SUM(amount), SUM(pv), SUM(bv)
			FROM `tabBusiness Transaction`
			WHERE distributor=%s
				AND DATE(posting_date)=%s
				AND docstatus < 2
			""",
			(distributor, day),
		)[0]
		amount_values.append(flt(row[0]))
		pv_values.append(flt(row[1]))
		bv_values.append(flt(row[2]))

	context.total_business = sum(amount_values)
	context.total_pv = sum(pv_values)
	context.total_bv = sum(bv_values)
	context.business_chart_labels = as_json(trend_days)
	context.business_amount_values = as_json(amount_values)
	context.business_pv_values = as_json(pv_values)
	context.business_bv_values = as_json(bv_values)

	commission_types = ["Direct", "Binary"]
	commission_type_values = [
		sum(flt(c.commission_amount) for c in commissions if c.commission_type == item)
		for item in commission_types
	]
	context.commission_type_labels = as_json(commission_types)
	context.commission_type_values = as_json(commission_type_values)

	context.commission_status_labels = as_json(["Paid", "Pending"])
	context.commission_status_values = as_json([context.paid_commission, context.pending_commission])

	wallet_credit_values = []
	wallet_debit_values = []
	if wallet_name:
		for day in trend_days:
			row = frappe.db.sql(
				"""
				SELECT
					SUM(CASE WHEN transaction_type='Credit' THEN amount ELSE 0 END),
					SUM(CASE WHEN transaction_type='Debit' THEN amount ELSE 0 END)
				FROM `tabWallet Transaction`
				WHERE wallet=%s
					AND DATE(posting_date)=%s
				""",
				(wallet_name, day),
			)[0]
			wallet_credit_values.append(flt(row[0]))
			wallet_debit_values.append(flt(row[1]))
	else:
		wallet_credit_values = [0 for _day in trend_days]
		wallet_debit_values = [0 for _day in trend_days]

	context.wallet_chart_labels = as_json(trend_days)
	context.wallet_credit_values = as_json(wallet_credit_values)
	context.wallet_debit_values = as_json(wallet_debit_values)
	context.wallet_mix_labels = as_json(["Credited", "Debited", "Balance"])
	context.wallet_mix_values = as_json([total_credit, total_debit, balance])

	context.network_labels = as_json(["Left", "Right"])
	context.network_values = as_json([left, right])

	insights = []
	if total_downline == 0:
		insights.append("Build the first downline member to activate network growth analytics.")
	elif balance_score < 55:
		insights.append(f"{context.weak_leg} leg needs attention. Current balance score is {balance_score}%.")

	if context.last_7_days_income == 0:
		insights.append("No commission was generated in the last 7 days.")
	elif context.last_7_days_income > (context.last_14_days_income - context.last_7_days_income):
		insights.append("Income is improving compared with the previous 7 days.")

	if context.pending_commission > 0:
		insights.append(f"Pending commission available for follow-up: ₹{context.pending_commission}.")

	if balance < 100:
		insights.append("Wallet balance is low; review payout readiness before withdrawal.")

	if context.total_business == 0:
		insights.append("No business volume was posted in the last 14 days.")

	context.insights = insights
