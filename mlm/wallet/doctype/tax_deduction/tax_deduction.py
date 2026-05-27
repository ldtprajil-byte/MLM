import frappe
from frappe.model.document import Document


class TaxDeduction(Document):
	def validate(self):
		self.validate_links()
		self.calculate_amounts()

	def validate_links(self):
		if not frappe.db.exists("Distributor", self.distributor):
			frappe.throw(f"Distributor {frappe.bold(self.distributor)} does not exist.")

		if self.payout_request and not frappe.db.exists("Payout Request", self.payout_request):
			frappe.throw(f"Payout Request {frappe.bold(self.payout_request)} does not exist.")

	def calculate_amounts(self):
		if not self.gross_amount or self.gross_amount <= 0:
			frappe.throw("Gross Amount must be greater than zero.")

		self.deduction_percent = self.deduction_percent or 0
		if self.deduction_percent < 0:
			frappe.throw("Deduction Percent cannot be negative.")

		if not self.deduction_amount:
			self.deduction_amount = self.gross_amount * self.deduction_percent / 100

		if self.deduction_amount < 0:
			frappe.throw("Deduction Amount cannot be negative.")

		if self.deduction_amount > self.gross_amount:
			frappe.throw("Deduction Amount cannot be greater than Gross Amount.")

		self.net_amount = self.gross_amount - self.deduction_amount
