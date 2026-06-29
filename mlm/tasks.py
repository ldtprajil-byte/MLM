import frappe
from mlm.distributor.doctype.distributor.distributor import check_and_update_rank, _check_rank_for_upline


def run_daily_rank_check():
	distributors = frappe.get_all(
		"Distributor",
		filters={"status": "Active", "is_active": 1},
		pluck="name",
	)
	for distributor in distributors:
		try:
			check_and_update_rank(distributor)
			frappe.db.commit()
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"Rank check failed for {distributor}")

	run_daily_binary_bonuses()


def run_daily_binary_bonuses():
	from mlm_multilevel.bonus.fast_start_bonus import sweep_fast_start_bonuses

	sweep_fast_start_bonuses(scheme="binary")


def run_monthly_binary_bonuses():
	from mlm_multilevel.bonus.car_bonus import process_monthly_car_bonus
	from mlm_multilevel.bonus.contest_bonus import process_contest_bonus
	from mlm_multilevel.bonus.generation_bonus import process_monthly_generation_bonus
	from mlm_multilevel.bonus.lifestyle_bonus import process_monthly_lifestyle_bonus

	process_monthly_car_bonus(scheme="binary")
	process_monthly_lifestyle_bonus(scheme="binary")
	process_monthly_generation_bonus(scheme="binary")
	process_contest_bonus(scheme="binary")


def run_weekly_roi_payout():
	"""Placeholder — will be implemented with Investment Plan logic"""
	pass


def run_weekly_roi_payout():
	"""Weekly scheduled job — credits ROI to active investors"""
	from mlm.wallet.utils import post_wallet_transaction

	today = frappe.utils.today()

	# Get all active ROI Ledgers
	active_ledgers = frappe.get_all(
		"ROI Ledger",
		filters={"status": "Active"},
		fields=[
			"name", "distributor", "investment_amount",
			"roi_percent", "end_date", "total_roi_paid",
			"last_paid_date", "source_transaction"
		],
	)

	for ledger in active_ledgers:
		try:
			# Check if plan has expired
			if str(today) > str(ledger.end_date):
				frappe.db.set_value("ROI Ledger", ledger.name, "status", "Completed")
				# Update distributor active investment
				current = frappe.db.get_value("Distributor", ledger.distributor, "active_investment") or 0
				frappe.db.set_value("Distributor", ledger.distributor, "active_investment", max(0, current - ledger.investment_amount))
				frappe.db.commit()
				continue

			# Skip if already paid this week
			if ledger.last_paid_date:
				days_since = frappe.utils.date_diff(today, ledger.last_paid_date)
				if days_since < 7:
					continue

			# Calculate weekly ROI
			weekly_roi = (ledger.investment_amount * ledger.roi_percent) / 100

			# Credit wallet
			post_wallet_transaction(
				distributor=ledger.distributor,
				transaction_type="Credit",
				amount=weekly_roi,
				reference_type="ROI Ledger",
				reference_name=ledger.name,
				remarks=f"Weekly ROI for investment {ledger.source_transaction}",
			)

			# Update ROI Ledger
			frappe.db.set_value(
				"ROI Ledger",
				ledger.name,
				{
					"total_roi_paid": (ledger.total_roi_paid or 0) + weekly_roi,
					"last_paid_date": today,
					"wallet_posted": 1,
				}
			)
			frappe.db.commit()
			frappe.logger().info(f"ROI credited ✅ {ledger.distributor} → ₹{weekly_roi}")

		except Exception:
			frappe.log_error(frappe.get_traceback(), f"ROI payout failed for {ledger.name}")
