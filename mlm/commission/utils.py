import frappe

from mlm.network.utils import BINARY, UNILEVEL, get_upline, normalize_plan_type


def get_active_commission_plan():
	plan = frappe.get_all(
		"Commission Plan",
		filters={"status": "Active"},
		fields=[
			"name",
			"plan_type",
			"direct_bonus_percent",
			"binary_bonus_percent",
			"generation_bonus_percent",
		],
		order_by="modified desc",
		limit=1,
	)
	if not plan:
		frappe.throw("Please create one Active Commission Plan before submitting transactions.")

	plan = plan[0]
	normalize_plan_type(plan.plan_type)
	return plan


def create_commissions_for_transaction(transaction):
	if frappe.db.exists("Commission Ledger", {"source_transaction": transaction.name}):
		return []

	plan = get_active_commission_plan()
	ledgers = []

	if plan.direct_bonus_percent:
		ledgers.extend(create_direct_commission(transaction, plan))

	if plan.plan_type == BINARY:
		ledgers.extend(create_binary_commissions(transaction, plan))
	elif plan.plan_type == UNILEVEL:
		ledgers.extend(create_generation_commissions(transaction, plan))

	return ledgers


def create_direct_commission(transaction, plan):
	sponsor = frappe.db.get_value("Distributor", transaction.distributor, "sponsor")
	if not sponsor:
		return []

	return [
		ledger
		for ledger in [
			create_commission_ledger(
				distributor=sponsor,
				source_distributor=transaction.distributor,
				source_transaction=transaction.name,
				commission_type="Direct",
				commission_percent=plan.direct_bonus_percent,
				base_amount=transaction.amount,
				remarks=f"Direct bonus from {transaction.distributor}",
			)
		]
		if ledger
	]


def create_generation_commissions(transaction, plan):
	if not plan.generation_bonus_percent:
		return []

	max_depth = get_max_depth()
	ledgers = []
	for upline in get_upline(transaction.distributor, plan_type=UNILEVEL, max_depth=max_depth):
		ledger = create_commission_ledger(
			distributor=upline["distributor"],
			source_distributor=transaction.distributor,
			source_transaction=transaction.name,
			commission_type="Generation",
			commission_percent=plan.generation_bonus_percent,
			base_amount=transaction.amount,
			remarks=f"Generation level {upline["level"]} bonus from {transaction.distributor}",
		)
		if ledger:
			ledgers.append(ledger)

	return ledgers


def create_binary_commissions(transaction, plan):
	if not plan.binary_bonus_percent:
		return []

	max_depth = get_max_depth()
	ledgers = []
	for upline in get_upline(transaction.distributor, plan_type=BINARY, max_depth=max_depth):
		leg_position = get_binary_source_leg(upline["distributor"], transaction.distributor)
		if not leg_position:
			continue

		ledger = create_commission_ledger(
			distributor=upline["distributor"],
			source_distributor=transaction.distributor,
			source_transaction=transaction.name,
			commission_type="Binary",
			commission_percent=plan.binary_bonus_percent,
			base_amount=transaction.bv,
			remarks=f"Binary {leg_position} leg level {upline["level"]} bonus from {transaction.distributor}",
		)
		if ledger:
			ledgers.append(ledger)

	return ledgers


def create_commission_ledger(
	distributor,
	source_distributor,
	source_transaction,
	commission_type,
	commission_percent,
	base_amount,
	remarks=None,
):
	commission_amount = (base_amount or 0) * (commission_percent or 0) / 100
	if commission_amount <= 0:
		return None

	distributor_name = frappe.db.get_value("Distributor", distributor, "distributor_name")
	source_distributor_name = frappe.db.get_value("Distributor", source_distributor, "distributor_name") if source_distributor else None

	doc = frappe.get_doc(
		{
			"doctype": "Commission Ledger",
			"distributor": distributor,
			"distributor_name": distributor,
			"source_distributor": source_distributor,
			"source_distributor_name": source_distributor,
			"source_transaction": source_transaction,
			"commission_type": commission_type,
			"status": "Pending",
			"commission_amount": commission_amount,
			"commission_percent": commission_percent,
			"wallet_posted": 0,
			"remarks": remarks,
		}
	).insert(ignore_permissions=True)
	doc.flags.ignore_permissions = True
	doc.submit()
	return doc


def get_binary_source_leg(ancestor, source_distributor):
	ancestor_path = get_tree_path(ancestor)
	source_path = get_tree_path(source_distributor)
	if not ancestor_path or not source_path or not source_path.startswith(ancestor_path):
		return None

	ancestor_parts = split_path(ancestor_path)
	source_parts = split_path(source_path)
	if len(source_parts) <= len(ancestor_parts):
		return None

	next_distributor = source_parts[len(ancestor_parts)]
	return frappe.db.get_value("Network Node", {"distributor": next_distributor}, "leg_position")


def get_tree_path(distributor):
	return frappe.db.get_value("Network Node", {"distributor": distributor}, "tree_path")


def split_path(path):
	return [part for part in (path or "").split("/") if part]


def get_max_depth():
	if frappe.db.exists("DocType", "MLM Settings"):
		try:
			max_depth = frappe.db.get_single_value("MLM Settings", "max_depth")
			return max_depth or None
		except Exception:
			return None

	return None
