import frappe
from frappe.model.document import Document
from mlm.network.utils import find_available_binary_position, BINARY
from mlm.wallet.utils import get_or_create_wallet


class Distributor(Document):
	def validate(self):
		self.validate_sponsor()
		self.validate_placement_parent()

	def after_insert(self):
		self.create_wallet()
		self.create_network_node()
		if self.sponsor:
			process_binary_fast_start_bonus(self.sponsor)

	def on_update(self):
		if self.status == "Active":
			check_and_update_rank(self.name)
			if self.sponsor:
				process_binary_fast_start_bonus(self.sponsor)

	# ─── Validation ───────────────────────────────────────────────

	def validate_sponsor(self):
		if not self.sponsor:
			return
		if self.sponsor == self.name:
			frappe.throw("Distributor cannot sponsor themselves.")
		if not frappe.db.exists("Distributor", self.sponsor):
			frappe.throw(f"Sponsor {frappe.bold(self.sponsor)} does not exist.")
		if self.name in get_sponsor_upline(self.sponsor):
			frappe.throw("Sponsor cannot be one of this distributor's downline members.")

	def validate_placement_parent(self):
		if not self.placement_parent and not self.leg_position:
			return
		if not self.placement_parent:
			frappe.throw("Placement Parent is required when Leg Position is selected.")
		if self.placement_parent == self.name:
			frappe.throw("Distributor cannot be placed under themselves.")
		if self.leg_position not in ("Left", "Right"):
			frappe.throw("Leg Position must be Left or Right.")
		if not frappe.db.exists("Distributor", self.placement_parent):
			frappe.throw(f"Placement Parent {frappe.bold(self.placement_parent)} does not exist.")

	# ─── Auto Create Wallet ───────────────────────────────────────

	def create_wallet(self):
		get_or_create_wallet(self.name)

	# ─── Auto Create Network Node ─────────────────────────────────

	def create_network_node(self):
		if frappe.db.exists("Network Node", {"distributor": self.name}):
			return

		plan_type = frappe.db.get_single_value("MLM Settings", "plan_type") or BINARY

		parent_distributor = self.placement_parent
		leg_position = self.leg_position

		# Auto find position if not manually set
		if not parent_distributor and self.sponsor and plan_type == BINARY:
			position = find_available_binary_position(self.sponsor)
			if position:
				parent_distributor = position.get("parent_distributor")
				leg_position = position.get("leg_position")

		# Build tree path
		if parent_distributor:
			parent_path = frappe.db.get_value(
				"Network Node", {"distributor": parent_distributor}, "tree_path"
			) or parent_distributor
			tree_path = f"{parent_path}/{self.name}"
			depth_level = len([p for p in tree_path.split("/") if p]) - 1
		else:
			tree_path = self.name
			depth_level = 0

		node = frappe.get_doc({
			"doctype": "Network Node",
			"distributor": self.name,
			"sponsor": self.sponsor,
			"parent_distributor": parent_distributor,
			"leg_position": leg_position,
			"tree_path": tree_path,
			"depth_level": depth_level,
			"left_count": 0,
			"right_count": 0,
			"is_root": 1 if not parent_distributor else 0,
		})
		node.insert(ignore_permissions=True)

		# Update parent left/right count
		if parent_distributor and leg_position:
			update_parent_counts(parent_distributor, leg_position)

		# Create placement log
		frappe.get_doc({
			"doctype": "Placement Log",
			"distributor": self.name,
			"new_parent": parent_distributor,
			"new_leg": leg_position,
			"reason": "Initial placement on joining",
			"changed_by": frappe.session.user,
			"changed_on": frappe.utils.now(),
		}).insert(ignore_permissions=True)


# ─── Rank Promotion ───────────────────────────────────────────────

def check_and_update_rank(distributor):
	from mlm.network.utils import get_downline, BINARY, UNILEVEL

	plan_type = frappe.db.get_single_value("MLM Settings", "plan_type") or UNILEVEL

	# Get personal PV
	last_volume = frappe.get_all(
		"Volume Ledger",
		filters={"distributor": distributor},
		fields=["running_pv", "running_bv"],
		order_by="creation desc",
		limit=1,
	)
	personal_pv = last_volume[0].running_pv if last_volume else 0

	# Get team BV — sum all downline running_bv
	downline = get_downline(distributor, plan_type=plan_type)
	team_bv = 0
	for member in downline:
		vol = frappe.get_all(
			"Volume Ledger",
			filters={"distributor": member.get("distributor")},
			fields=["running_bv"],
			order_by="creation desc",
			limit=1,
		)
		if vol:
			team_bv += vol[0].running_bv or 0

	# Get all active ranks ordered by priority
	ranks = frappe.get_all(
		"Rank",
		filters={"is_active": 1},
		fields=["name", "min_pv", "min_team_pv", "priority"],
		order_by="priority desc",
	)

	# Find highest qualifying rank
	qualified_rank = None
	for rank in ranks:
		if personal_pv >= (rank.min_pv or 0) and team_bv >= (rank.min_team_pv or 0):
			qualified_rank = rank.name
			break

	if not qualified_rank:
		return

	current_rank = frappe.db.get_value("Distributor", distributor, "current_rank")

	if current_rank == qualified_rank:
		return

	# Determine promotion or demotion
	current_priority = frappe.db.get_value("Rank", current_rank, "priority") or 0
	new_priority = frappe.db.get_value("Rank", qualified_rank, "priority") or 0
	change_type = "Promotion" if new_priority > current_priority else "Demotion"

	# Update rank
	frappe.db.set_value("Distributor", distributor, "current_rank", qualified_rank)

	# Create Rank Log
	rank_log = frappe.get_doc({
		"doctype": "Rank Log",
		"distributor": distributor,
		"old_rank": current_rank,
		"new_rank": qualified_rank,
		"change_type": change_type,
		"personal_pv": personal_pv,
		"team_bv": team_bv,
		"triggered_by": "Transaction",
		"date": frappe.utils.today(),
		"remarks": f"Auto rank update from {current_rank} to {qualified_rank}",
	}).insert(ignore_permissions=True)

	if change_type == "Promotion":
		from mlm_multilevel.bonus.rank_bonus import process_rank_advancement_bonus

		process_rank_advancement_bonus(
			distributor,
			qualified_rank,
			rank_log=rank_log,
			scheme="binary",
		)


# ─── Helpers ──────────────────────────────────────────────────────

def get_sponsor_upline(distributor):
	upline = []
	current = distributor
	visited = set()
	while current:
		if current in visited:
			frappe.throw("Circular sponsor relationship detected.")
		visited.add(current)
		sponsor = frappe.db.get_value("Distributor", current, "sponsor")
		if not sponsor:
			break
		upline.append(sponsor)
		current = sponsor
	return upline


def update_parent_counts(parent_distributor, leg_position):
	field = "left_count" if leg_position == "Left" else "right_count"
	current = frappe.db.get_value("Network Node", {"distributor": parent_distributor}, field) or 0
	frappe.db.set_value(
		"Network Node",
		{"distributor": parent_distributor},
		field,
		current + 1,
		update_modified=False,
	)


# ─── Hook: fired after Business Transaction submit ────────────────

def on_business_transaction_submit(doc, method):
	_check_rank_for_upline(doc.distributor)


def _check_rank_for_upline(distributor):
	"""Check rank for distributor and all their upline"""
	from mlm.network.utils import get_upline, BINARY, UNILEVEL
	plan_type = frappe.db.get_single_value("MLM Settings", "plan_type") or UNILEVEL

	# Check rank for the distributor themselves
	check_and_update_rank(distributor)

	# Check rank for all upline
	upline = get_upline(distributor, plan_type=plan_type)
	for member in upline:
		try:
			check_and_update_rank(member.get("distributor"))
			frappe.db.commit()
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Rank check failed for {member.get('distributor')}")


def process_binary_fast_start_bonus(distributor):
	try:
		from mlm_multilevel.bonus.fast_start_bonus import process_fast_start_bonus

		process_fast_start_bonus(distributor, scheme="binary")
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			f"Binary Fast Start Bonus error for {distributor}",
		)
