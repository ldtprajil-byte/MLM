import frappe
from frappe.model.document import Document


class WalletTransaction(Document):
	def validate(self):
		if self.transaction_type not in ("Credit", "Debit"):
			frappe.throw("Transaction Type must be Credit or Debit.")

		if not self.amount or self.amount <= 0:
			frappe.throw("Wallet Transaction amount must be greater than zero.")

		if self.wallet and not frappe.db.exists("Wallet", self.wallet):
			frappe.throw(f"Wallet {frappe.bold(self.wallet)} does not exist.")
