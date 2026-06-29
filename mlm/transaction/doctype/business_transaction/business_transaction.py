import frappe
from frappe.model.document import Document
from frappe.utils import now

from mlm.commission.utils import create_commissions_for_transaction


class BusinessTransaction(Document):

	def validate(self):
		self.validate_distributor()
		self.validate_amounts()

	def on_submit(self):
		self.db_set("status", "Paid", update_modified=False)
		self.create_volume_ledger()
		create_commissions_for_transaction(self)
		create_roi_ledger(self)

	def on_cancel(self):
		check_commissions_not_withdrawn(self.name)
		self.create_volume_ledger(is_reversal=True)
		self.cancel_commission_ledgers()
		self.cancel_bonus_ledgers()
		self.db_set("status", "Cancelled", update_modified=False)

	def on_trash(self):
		frappe.throw("Business Transactions cannot be deleted.")

	def validate_distributor(self):
		if not frappe.db.exists("Distributor", self.distributor):
			frappe.throw(f"Distributor {frappe.bold(self.distributor)} does not exist.")

	def validate_amounts(self):
		if not self.amount or self.amount <= 0:
			frappe.throw("Amount must be greater than zero.")
		if self.pv is None:
			self.pv = 0
		if self.bv is None:
			self.bv = self.amount
		if self.pv < 0 or self.bv < 0:
			frappe.throw("PV and BV cannot be negative.")

	def create_volume_ledger(self, is_reversal=False):
		pv_credit = -(self.pv or 0) if is_reversal else (self.pv or 0)
		bv_credit = -(self.bv or 0) if is_reversal else (self.bv or 0)

		if frappe.db.exists(
			"Volume Ledger",
			{
				"source_transaction": self.name,
				"pv_credit": pv_credit,
				"bv_credit": bv_credit,
			},
		):
			return

		running = get_running_volume(self.distributor)
		frappe.get_doc({
			"doctype": "Volume Ledger",
			"distributor": self.distributor,
			"source_transaction": self.name,
			"posting_date": now(),
			"pv_credit": pv_credit,
			"bv_credit": bv_credit,
			"running_pv": running["pv"] + pv_credit,
			"running_bv": running["bv"] + bv_credit,
		}).insert(ignore_permissions=True)

	def cancel_commission_ledgers(self):
		ledgers = frappe.get_all(
			"Commission Ledger",
			filters={"source_transaction": self.name, "docstatus": 1},
			pluck="name",
		)
		for ledger in ledgers:
			doc = frappe.get_doc("Commission Ledger", ledger)
			doc.flags.ignore_permissions = True
			doc.cancel()

	def cancel_bonus_ledgers(self):
		if not frappe.db.exists("DocType", "Bonus Ledger"):
			return

		ledgers = frappe.get_all(
			"Bonus Ledger",
			filters={
				"source_transaction_type": "Business Transaction",
				"source_transaction": self.name,
				"docstatus": 1,
			},
			pluck="name",
		)
		for ledger in ledgers:
			doc = frappe.get_doc("Bonus Ledger", ledger)
			doc.flags.ignore_permissions = True
			doc.cancel()


def get_running_volume(distributor):
	last_entry = frappe.get_all(
		"Volume Ledger",
		filters={"distributor": distributor},
		fields=["running_pv", "running_bv"],
		order_by="creation desc",
		limit=1,
	)
	if not last_entry:
		return {"pv": 0, "bv": 0}
	return {
		"pv": last_entry[0].running_pv or 0,
		"bv": last_entry[0].running_bv or 0,
	}


def check_commissions_not_withdrawn(transaction_name):
	commission_ledgers = frappe.get_all(
		"Commission Ledger",
		filters={
			"source_transaction": transaction_name,
			"docstatus": 1,
			"wallet_posted": 1,
		},
		fields=["name", "distributor", "commission_amount"],
	)
	for ledger in commission_ledgers:
		payout = frappe.get_all(
			"Payout Request",
			filters={
				"distributor": ledger.distributor,
				"status": "Paid",
				"docstatus": 1,
			},
			limit=1,
		)
		if payout:
			frappe.throw(
				f"Cannot cancel — commission of {ledger.commission_amount} "
				f"for {frappe.bold(ledger.distributor)} has already been paid out. "
				f"Please reverse the payout first."
			)


# ─── Hook: fired after Business Transaction submit ────────────────

def on_business_transaction_submit(doc, method):
	from mlm.distributor.doctype.distributor.distributor import check_and_update_rank
	check_and_update_rank(doc.distributor)

def create_roi_ledger(transaction):
	"""Create ROI Ledger when Investment transaction is submitted"""
	if transaction.transaction_type != "Investment":
		return

	if not transaction.reference_name:
		frappe.throw("Please select an Investment Plan in Reference Name field.")

	if not frappe.db.exists("Investment Plan", transaction.reference_name):
		frappe.throw(f"Investment Plan {transaction.reference_name} does not exist.")

	plan = frappe.get_doc("Investment Plan", transaction.reference_name)

	if not plan.is_active:
		frappe.throw(f"Investment Plan {plan.plan_name} is not active.")

	start_date = transaction.posting_date
	end_date = frappe.utils.add_days(start_date, plan.duration_days)

	# Check if ROI Ledger already exists
	if frappe.db.exists("ROI Ledger", {"source_transaction": transaction.name}):
		return

	frappe.get_doc({
		"doctype": "ROI Ledger",
		"distributor": transaction.distributor,
		"source_transaction": transaction.name,
		"investment_plan": plan.name,
		"investment_amount": transaction.amount,
		"roi_percent": plan.roi_percent,
		"duration_days": plan.duration_days,
		"start_date": start_date,
		"end_date": end_date,
		"total_roi_paid": 0,
		"last_paid_date": None,
		"status": "Active",
		"wallet_posted": 0,
	}).insert(ignore_permissions=True)

	# Update distributor investment fields
	frappe.db.set_value(
		"Distributor",
		transaction.distributor,
		{
			"total_investment": (frappe.db.get_value("Distributor", transaction.distributor, "total_investment") or 0) + transaction.amount,
			"active_investment": (frappe.db.get_value("Distributor", transaction.distributor, "active_investment") or 0) + transaction.amount,
		}
	)
	frappe.db.commit()
