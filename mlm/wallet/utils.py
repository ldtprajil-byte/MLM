import frappe
from frappe.utils import now


def get_or_create_wallet(distributor):
	if not frappe.db.exists("Distributor", distributor):
		frappe.throw(f"Distributor {frappe.bold(distributor)} does not exist.")

	wallet = frappe.db.exists("Wallet", {"distributor": distributor})
	if wallet:
		return wallet

	return (
		frappe.get_doc(
			{
				"doctype": "Wallet",
				"distributor": distributor,
				"current_balance": 0,
				"total_credit": 0,
				"total_debit": 0,
				"last_updated": now(),
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def post_wallet_transaction(distributor, transaction_type, amount, reference_type=None, reference_name=None, remarks=None):
	if amount <= 0:
		frappe.throw("Wallet transaction amount must be greater than zero.")

	if transaction_type not in ("Credit", "Debit"):
		frappe.throw("Wallet transaction type must be Credit or Debit.")

	wallet = get_or_create_wallet(distributor)
	wallet_doc = frappe.get_doc("Wallet", wallet)
	balance_before = wallet_doc.current_balance or 0
	balance_after = balance_before + amount if transaction_type == "Credit" else balance_before - amount

	if balance_after < 0:
		frappe.throw(f"Insufficient wallet balance for {frappe.bold(distributor)}.")

	wallet_transaction = frappe.get_doc(
		{
			"doctype": "Wallet Transaction",
			"wallet": wallet,
			"transaction_type": transaction_type,
			"amount": amount,
			"posting_date": now(),
			"balance_before": balance_before,
			"balance_after": balance_after,
			"reference_type": reference_type,
			"reference_name": reference_name,
			"remarks": remarks,
		}
	).insert(ignore_permissions=True)

	credit = amount if transaction_type == "Credit" else 0
	debit = amount if transaction_type == "Debit" else 0
	frappe.db.set_value(
		"Wallet",
		wallet,
		{
			"current_balance": balance_after,
			"total_credit": (wallet_doc.total_credit or 0) + credit,
			"total_debit": (wallet_doc.total_debit or 0) + debit,
			"last_updated": now(),
		},
		update_modified=False,
	)
	frappe.db.set_value("Distributor", distributor, "wallet_balance", balance_after, update_modified=False)

	return wallet_transaction
