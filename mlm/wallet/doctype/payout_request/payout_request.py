import frappe
from frappe.model.document import Document
from frappe.utils import now, today

from mlm.wallet.utils import get_or_create_wallet, post_wallet_transaction


class PayoutRequest(Document):
	def validate(self):
		self.set_defaults()
		self.validate_distributor()
		self.validate_amounts()
		self.validate_payout_method()
		self.validate_wallet_balance()
		self.validate_kyc()

	def on_submit(self):
		self.validate_not_already_paid()
		self.create_tax_deductions()
		post_wallet_transaction(
			distributor=self.distributor,
			transaction_type="Debit",
			amount=self.request_amount,
			reference_type=self.doctype,
			reference_name=self.name,
			remarks=f"Payout request {self.name}",
		)
		self.db_set("status", "Paid", update_modified=False)
		self.db_set("approved_by", frappe.session.user, update_modified=False)
		self.db_set("approved_on", now(), update_modified=False)

	def on_cancel(self):
		self.cancel_tax_deductions()
		post_wallet_transaction(
			distributor=self.distributor,
			transaction_type="Credit",
			amount=self.request_amount,
			reference_type=self.doctype,
			reference_name=self.name,
			remarks=f"Reversal for payout request {self.name}",
		)
		self.db_set("status", "Pending", update_modified=False)

	def set_defaults(self):
		if not self.status:
			self.status = "Pending"

		if not self.request_date:
			self.request_date = now()

		if self.distributor and not self.wallet:
			self.wallet = get_or_create_wallet(self.distributor)

		self.charges = self.charges or 0
		if self.request_amount:
			self.net_amount = self.request_amount - self.charges

	def validate_distributor(self):
		if not frappe.db.exists("Distributor", self.distributor):
			frappe.throw(f"Distributor {frappe.bold(self.distributor)} does not exist.")

		if not self.wallet:
			frappe.throw("Wallet is required.")

		wallet_distributor = frappe.db.get_value("Wallet", self.wallet, "distributor")
		if wallet_distributor != self.distributor:
			frappe.throw("Selected wallet does not belong to this distributor.")

	def validate_amounts(self):
		if not self.request_amount or self.request_amount <= 0:
			frappe.throw("Request Amount must be greater than zero.")

		if self.charges < 0:
			frappe.throw("Charges cannot be negative.")

		if self.charges > self.request_amount:
			frappe.throw("Charges cannot be greater than Request Amount.")

		self.net_amount = self.request_amount - self.charges

	def validate_payout_method(self):
		if self.payout_method == "UPI" and not self.upi_id:
			frappe.throw("UPI ID is required for UPI payout.")

		if self.payout_method == "Bank" and not self.bank_account:
			frappe.throw("Bank Account is required for Bank payout.")

	def validate_wallet_balance(self):
		balance = frappe.db.get_value("Wallet", self.wallet, "current_balance") or 0
		if balance < self.request_amount:
			frappe.throw(f"Insufficient Balance! Available balance is ₹{frappe.utils.fmt_money(balance)}. Please reduce your withdrawal amount.")

	def validate_kyc(self):
		if has_verified_kyc(self.distributor):
			return

		frappe.throw("Verified KYC is required before payout.")

	def validate_not_already_paid(self):
		if frappe.db.exists(
			"Wallet Transaction",
			{
				"reference_type": self.doctype,
				"reference_name": self.name,
				"transaction_type": "Debit",
			},
		):
			frappe.throw("Wallet debit already exists for this payout request.")

	def create_tax_deductions(self):
		if not self.charges:
			return

		if frappe.db.exists("Tax Deduction", {"payout_request": self.name, "docstatus": ["!=", 2]}):
			return

		doc = frappe.get_doc(
			{
				"doctype": "Tax Deduction",
				"distributor": self.distributor,
				"payout_request": self.name,
				"deduction_type": "Platform Fee",
				"posting_date": today(),
				"gross_amount": self.request_amount,
				"deduction_percent": 0,
				"deduction_amount": self.charges,
				"net_amount": self.net_amount,
				"remarks": f"Charges deducted for payout request {self.name}",
			}
		).insert(ignore_permissions=True)
		doc.flags.ignore_permissions = True
		doc.submit()

	def cancel_tax_deductions(self):
		tax_deductions = frappe.get_all(
			"Tax Deduction",
			filters={"payout_request": self.name, "docstatus": 1},
			pluck="name",
		)
		for tax_deduction in tax_deductions:
			doc = frappe.get_doc("Tax Deduction", tax_deduction)
			doc.flags.ignore_permissions = True
			doc.cancel()


def has_verified_kyc(distributor):
	kyc_rows = frappe.get_all(
		"Distributor KYC",
		filters={
			"parenttype": "Distributor",
			"parent": distributor,
			"verified": 1,
		},
		limit=1,
	)
	return bool(kyc_rows)
