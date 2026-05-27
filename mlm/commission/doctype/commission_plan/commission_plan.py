import frappe
from frappe.model.document import Document

from mlm.network.utils import BINARY, UNILEVEL, normalize_plan_type


class CommissionPlan(Document):
	def validate(self):
		normalize_plan_type(self.plan_type)
		self.validate_bonus_configuration()

	def validate_bonus_configuration(self):
		if self.plan_type == BINARY:
			self.validate_binary_plan()
			return

		if self.plan_type == UNILEVEL:
			self.validate_unilevel_plan()

	def validate_binary_plan(self):
		if not self.binary_bonus_percent:
			frappe.throw("Binary Bonus % is required for Binary commission plans.")

	def validate_unilevel_plan(self):
		if not self.generation_bonus_percent and not self.direct_bonus_percent:
			frappe.throw("Direct Bonus % or Generation Bonus % is required for Unilevel commission plans.")
