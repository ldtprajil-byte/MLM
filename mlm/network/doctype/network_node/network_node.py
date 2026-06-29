import frappe
from frappe.model.document import Document
from frappe.utils import now


class NetworkNode(Document):
	def validate(self):
		self.flags.was_new = self.is_new()
		self.set_root_status()
		self.validate_distributor()
		self.validate_parent_and_leg()
		self.set_old_placement()
		self.validate_unique_distributor()
		self.validate_existing_subtree_move()
		self.validate_slot_available()
		self.validate_not_circular()
		self.set_tree_details()
		self.set_counts()

	def on_update(self):
		self.sync_distributor_placement()
		self.create_placement_log()
		self.refresh_related_counts()

	def on_trash(self):
		self.validate_no_children()
		self.clear_distributor_placement()
		self.create_placement_log(is_delete=True)

	def after_delete(self):
		self.refresh_related_counts()

	def set_root_status(self):
		self.is_root = 0 if self.parent_distributor else 1
		if self.is_root:
			self.leg_position = None

	def validate_distributor(self):
		if not self.distributor:
			frappe.throw("Distributor is required.")

		if not frappe.db.exists("Distributor", self.distributor):
			frappe.throw(f"Distributor {frappe.bold(self.distributor)} does not exist.")

		if self.sponsor and not frappe.db.exists("Distributor", self.sponsor):
			frappe.throw(f"Sponsor {frappe.bold(self.sponsor)} does not exist.")

	def validate_parent_and_leg(self):
		if self.is_root:
			if self.parent_distributor:
				frappe.throw("Root node cannot have a placement parent.")
			return

		if not self.parent_distributor:
			frappe.throw("Placement parent is required for non-root network nodes.")

		if not frappe.db.exists("Distributor", self.parent_distributor):
			frappe.throw(f"Placement parent {frappe.bold(self.parent_distributor)} does not exist.")

		if not frappe.db.exists("Network Node", {"distributor": self.parent_distributor}):
			frappe.throw("Placement parent must already have a Network Node.")

		if self.parent_distributor == self.distributor:
			frappe.throw("A distributor cannot be placed under themselves.")

		if self.leg_position not in ("Left", "Right"):
			frappe.throw("Leg Position must be Left or Right for non-root network nodes.")

	def validate_unique_distributor(self):
		existing = frappe.db.exists(
			"Network Node",
			{
				"distributor": self.distributor,
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(f"Distributor already has a Network Node: {frappe.bold(existing)}.")

	def validate_slot_available(self):
		if self.is_root:
			existing_root = frappe.db.exists(
				"Network Node",
				{
					"is_root": 1,
					"name": ["!=", self.name],
				},
			)
			if existing_root:
				frappe.throw(f"Root Network Node already exists: {frappe.bold(existing_root)}.")
			return

		existing = frappe.db.exists(
			"Network Node",
			{
				"parent_distributor": self.parent_distributor,
				"leg_position": self.leg_position,
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				f"{self.leg_position} leg under {frappe.bold(self.parent_distributor)} is already occupied."
			)

	def validate_existing_subtree_move(self):
		old_placement = getattr(self.flags, "old_placement", None) or {}
		old_parent = old_placement.get("old_parent")
		old_leg = old_placement.get("old_leg")

		placement_changed = old_parent != self.parent_distributor or old_leg != self.leg_position
		if not placement_changed or not old_placement:
			return

		child = frappe.db.exists("Network Node", {"parent_distributor": self.distributor})
		if child:
			frappe.throw("Cannot move a Network Node that already has child nodes.")

	def validate_not_circular(self):
		if self.is_root:
			return

		parent_node = get_node_by_distributor(self.parent_distributor)
		if parent_node and self.distributor in split_tree_path(parent_node.tree_path):
			frappe.throw("A distributor cannot be placed under one of their own descendants.")

	def set_tree_details(self):
		if self.is_root:
			self.tree_path = make_tree_path([self.distributor])
			self.depth_level = 0
			return

		parent_node = get_node_by_distributor(self.parent_distributor)
		parent_path = split_tree_path(parent_node.tree_path)

		self.tree_path = make_tree_path([*parent_path, self.distributor])
		self.depth_level = len(parent_path)

	def set_counts(self):
		self.left_count = get_leg_count(self.distributor, "Left")
		self.right_count = get_leg_count(self.distributor, "Right")

	def set_old_placement(self):
		old_doc = self.get_doc_before_save()
		if old_doc:
			self.flags.old_placement = {
				"old_parent": old_doc.parent_distributor,
				"old_leg": old_doc.leg_position,
			}
			return

		self.flags.old_placement = {
			"old_parent": None,
			"old_leg": None,
		}

	def sync_distributor(self):
		distributor_name = frappe.db.get_value(
			"UL Distributor",
			self.distributor,
			"distributor_name",
		)
		frappe.db.set_value(
			"UL Distributor",
			self.distributor,
			{
				"sponsor": self.sponsor,
				"placement_parent": self.parent_distributor,
			},
			update_modified=False,
		)
		frappe.db.set_value(
			"UL Network Node",
			self.name,
			"distributor_name",
			distributor_name,
			update_modified=False,
		)
	def clear_distributor_placement(self):
		frappe.db.set_value(
			"Distributor",
			self.distributor,
			{
				"placement_parent": None,
				"leg_position": None,
			},
			update_modified=False,
		)

	def create_placement_log(self, is_delete=False):
		old_placement = getattr(self.flags, "old_placement", None) or {}
		old_parent = old_placement.get("old_parent")
		old_leg = old_placement.get("old_leg")
		if is_delete:
			old_parent = self.parent_distributor
			old_leg = self.leg_position

		new_parent = None if is_delete else self.parent_distributor
		new_leg = None if is_delete else self.leg_position

		was_new = getattr(self.flags, "was_new", False)
		if old_parent == new_parent and old_leg == new_leg and not was_new and not is_delete:
			return

		reason = "Network node deleted" if is_delete else "Network node placement updated"
		if was_new:
			reason = "Network node created"

		frappe.get_doc(
			{
				"doctype": "Placement Log",
				"distributor": self.distributor,
				"changed_by": frappe.session.user,
				"changed_on": now(),
				"old_parent": old_parent,
				"old_leg": old_leg,
				"new_parent": new_parent,
				"new_leg": new_leg,
				"reason": reason,
			}
		).insert(ignore_permissions=True)

	def refresh_related_counts(self):
		distributors = {self.distributor}
		old_placement = getattr(self.flags, "old_placement", None) or {}

		for distributor in (self.parent_distributor, old_placement.get("old_parent")):
			distributors.update(get_ancestor_distributors(distributor))

		for distributor in distributors:
			update_node_counts(distributor)

	def validate_no_children(self):
		child = frappe.db.exists("Network Node", {"parent_distributor": self.distributor})
		if child:
			frappe.throw("Cannot delete a Network Node that has child nodes.")


def get_node_by_distributor(distributor):
	if not distributor:
		return None

	name = frappe.db.exists("Network Node", {"distributor": distributor})
	if not name:
		return None

	return frappe.get_doc("Network Node", name)


def split_tree_path(tree_path):
	if not tree_path:
		return []

	return [part for part in tree_path.split("/") if part]


def make_tree_path(distributors):
	return "/" + "/".join(distributors) + "/"


def get_ancestor_distributors(distributor):
	node = get_node_by_distributor(distributor)
	if not node:
		return []

	return split_tree_path(node.tree_path)


def get_leg_count(distributor, leg_position):
	child_name = frappe.db.exists(
		"Network Node",
		{
			"parent_distributor": distributor,
			"leg_position": leg_position,
		},
	)
	if not child_name:
		return 0

	child_path = frappe.db.get_value("Network Node", child_name, "tree_path")
	if not child_path:
		return 0

	return frappe.db.count("Network Node", {"tree_path": ["like", f"{child_path}%"]})


def update_node_counts(distributor):
	node_name = frappe.db.exists("Network Node", {"distributor": distributor})
	if not node_name:
		return

	frappe.db.set_value(
		"Network Node",
		node_name,
		{
			"left_count": get_leg_count(distributor, "Left"),
			"right_count": get_leg_count(distributor, "Right"),
		},
		update_modified=False,
	)
