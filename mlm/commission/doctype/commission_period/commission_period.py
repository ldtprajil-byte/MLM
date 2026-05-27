import frappe
from frappe.model.document import Document
from frappe.utils import now


class CommissionPeriod(Document):
	def validate(self):
		self.validate_dates()

	def validate_dates(self):
		if self.start_date and self.end_date:
			if self.start_date > self.end_date:
				frappe.throw("Start Date cannot be after End Date.")

	def on_submit(self):
		self.db_set("status", "Open", update_modified=False)


def create_commission_period():
	"""Scheduled job — runs on 1st of every month to create new period"""
	from frappe.utils import today, get_first_day, get_last_day
	import datetime

	first_day = get_first_day(today())
	last_day = get_last_day(today())
	period_name = first_day.strftime("%B %Y")

	if frappe.db.exists("Commission Period", {"period_name": period_name}):
		frappe.logger().info(f"Commission Period {period_name} already exists.")
		return

	period = frappe.get_doc({
		"doctype": "Commission Period",
		"period_name": period_name,
		"start_date": first_day,
		"end_date": last_day,
		"status": "Open",
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.logger().info(f"Commission Period {period_name} created ✅")


def close_commission_period():
	"""Scheduled job — runs on last day of every month to close period"""
	from frappe.utils import today, get_last_day

	last_day = get_last_day(today())

	# Only run on last day of month
	if str(today()) != str(last_day):
		return

	# Find open period for this month
	period = frappe.get_all(
		"Commission Period",
		filters={"status": "Open", "end_date": last_day},
		limit=1,
	)
	if not period:
		frappe.logger().info("No open Commission Period found to close.")
		return

	period_doc = frappe.get_doc("Commission Period", period[0].name)
	_process_period(period_doc)


def _process_period(period_doc):
	"""Link commissions to period, calculate totals, close period"""

	# Get all commission ledgers in this period date range
	ledgers = frappe.get_all(
		"Commission Ledger",
		filters={
			"docstatus": 1,
			"commission_period": ["in", ["", None]],
			"creation": ["between", [
				str(period_doc.start_date) + " 00:00:00",
				str(period_doc.end_date) + " 23:59:59",
			]],
		},
		fields=["name", "distributor", "commission_amount"],
	)

	if not ledgers:
		frappe.logger().info(f"No commissions found for period {period_doc.period_name}")
		return

	total_commission = 0
	distributors = set()

	for ledger in ledgers:
		# Link commission to this period
		frappe.db.set_value(
			"Commission Ledger",
			ledger.name,
			"commission_period",
			period_doc.name,
			update_modified=False,
		)
		total_commission += ledger.commission_amount or 0
		distributors.add(ledger.distributor)

	# Update period totals and close
	frappe.db.set_value(
		"Commission Period",
		period_doc.name,
		{
			"status": "Closed",
			"calculated_on": now(),
			"closed_on": now(),
			"total_commission": total_commission,
			"total_distributors": len(distributors),
		},
		update_modified=False,
	)
	frappe.db.commit()
	frappe.logger().info(
		f"Commission Period {period_doc.period_name} closed ✅ "
		f"Total: {total_commission}, Distributors: {len(distributors)}"
	)
