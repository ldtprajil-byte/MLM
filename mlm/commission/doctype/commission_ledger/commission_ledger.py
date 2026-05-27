import frappe
from frappe.model.document import Document

from mlm.wallet.utils import post_wallet_transaction


class CommissionLedger(Document):
	def validate(self):
		self.validate_amount()

	def on_submit(self):
		if self.wallet_posted:
			return

		post_wallet_transaction(
			distributor=self.distributor,
			transaction_type="Credit",
			amount=self.commission_amount,
			reference_type=self.doctype,
			reference_name=self.name,
			remarks=f"{self.commission_type} commission from {self.source_transaction or self.source_distributor or ''}",
		)
		self.db_set("wallet_posted", 1, update_modified=False)
		self.db_set("status", "Paid", update_modified=False)

	def on_cancel(self):
		if not self.wallet_posted:
			return

		post_wallet_transaction(
			distributor=self.distributor,
			transaction_type="Debit",
			amount=self.commission_amount,
			reference_type=self.doctype,
			reference_name=self.name,
			remarks=f"Reversal for {self.commission_type} commission {self.name}",
		)
		self.db_set("wallet_posted", 0, update_modified=False)
		self.db_set("status", "Pending", update_modified=False)

	def validate_amount(self):
		if not self.commission_amount or self.commission_amount <= 0:
			frappe.throw("Commission Amount must be greater than zero.")
