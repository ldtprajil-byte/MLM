import frappe
from frappe.model.document import Document


class VolumeLedger(Document):
	def validate(self):
		if not frappe.db.exists("Distributor", self.distributor):
			frappe.throw(f"Distributor {frappe.bold(self.distributor)} does not exist.")

		if not frappe.db.exists("Business Transaction", self.source_transaction):
			frappe.throw(f"Business Transaction {frappe.bold(self.source_transaction)} does not exist.")

		self.pv_credit = self.pv_credit or 0
		self.bv_credit = self.bv_credit or 0
