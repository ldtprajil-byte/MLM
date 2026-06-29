import frappe
from frappe.model.document import Document

from mlm.network.utils import BINARY, UNILEVEL,MATRIX, normalize_plan_type


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
			return

		if self.plan_type == MATRIX:
			self.validate_matrix_plan()
			return

	def validate_binary_plan(self):
		if not self.binary_bonus_percent:
			frappe.throw("Binary Bonus % is required for Binary commission plans.")

	def validate_unilevel_plan(self):
		if not self.max_payout_depth:
			frappe.throw("Max Payout Depth is required for Unilevel commission plans.")

		if not self.max_compression_depth:
			frappe.throw("Max Compression Depth is required for Unilevel commission plans.")

		if not self.default_product_commission_rate:
			frappe.throw("Default Product Commission Rate is required for Unilevel commission plans.")

		if not self.commission_plan_level:
			frappe.throw("At least one Commission Plan Level is required for Unilevel commission plans.")

		levels = set()
		for row in self.commission_plan_level:
			if not row.level_no:
				frappe.throw("Level No is required in Commission Plan Level.")

			if row.level_no in levels:
				frappe.throw(f"Duplicate Unilevel commission level: {row.level_no}")

			if row.level_no > self.max_payout_depth:
				frappe.throw(
					f"Level {row.level_no} cannot be greater than Max Payout Depth."
				)

			if not row.commission_percent:
				frappe.throw(f"Commission Percent is required for level {row.level_no}.")

			levels.add(row.level_no)

    
	def validate_matrix_plan(self):

		if not self.matrix_width:
			frappe.throw("Matrix Width is required.")

		if not self.matrix_depth:
			frappe.throw("Matrix Depth is required.")

		if not self.default_product_commission_rate:
			frappe.throw(
				"Default Product Commission Rate is required."
			)

		if not self.commission_plan_level:
			frappe.throw(
				"At least one Commission Plan Level is required."
			)
