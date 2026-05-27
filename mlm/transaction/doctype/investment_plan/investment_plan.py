import frappe
from frappe.model.document import Document

class InvestmentPlan(Document):
	def validate(self):
		if self.roi_percent <= 0:
			frappe.throw("ROI Percent must be greater than zero.")
		if self.duration_days <= 0:
			frappe.throw("Duration Days must be greater than zero.")
		if self.investment_amount <= 0:
			frappe.throw("Investment Amount must be greater than zero.")
