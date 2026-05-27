import frappe

BINARY = "Binary"
UNILEVEL = "Unilevel"


def normalize_plan_type(plan_type):
	if plan_type not in (BINARY, UNILEVEL):
		frappe.throw(f"Unsupported commission plan type: {frappe.bold(plan_type)}.")

	return plan_type


def get_upline(distributor, plan_type=UNILEVEL, max_depth=None):
	plan_type = normalize_plan_type(plan_type)
	parent_field = get_parent_field(plan_type)
	upline = []
	current = distributor
	depth = 0
	visited = set()

	while current:
		if current in visited:
			frappe.throw("Circular distributor relationship detected.")

		visited.add(current)
		parent = frappe.db.get_value("Distributor", current, parent_field)
		if not parent:
			break

		depth += 1
		upline.append({"distributor": parent, "level": depth})
		current = parent

		if max_depth and depth >= max_depth:
			break

	return upline


def get_downline(distributor, plan_type=UNILEVEL, max_depth=None):
	plan_type = normalize_plan_type(plan_type)

	if plan_type == BINARY:
		return get_binary_downline(distributor, max_depth=max_depth)

	return get_unilevel_downline(distributor, max_depth=max_depth)


def get_unilevel_downline(distributor, max_depth=None):
	return get_child_downline(
		distributor=distributor,
		filters={"sponsor": distributor},
		child_fields=["name"],
		max_depth=max_depth,
	)


def get_binary_downline(distributor, leg_position=None, max_depth=None):
	filters = {"parent_distributor": distributor}
	if leg_position:
		filters["leg_position"] = leg_position

	return get_child_downline(
		distributor=distributor,
		filters=filters,
		child_fields=["distributor", "leg_position"],
		max_depth=max_depth,
		doctype="Network Node",
		parent_field="parent_distributor",
	)


def get_child_downline(
	distributor,
	filters,
	child_fields,
	max_depth=None,
	doctype="Distributor",
	parent_field="sponsor",
):
	downline = []
	queue = [(distributor, 0)]
	visited = set()

	while queue:
		parent, depth = queue.pop(0)
		if max_depth and depth >= max_depth:
			continue

		child_filters = dict(filters)
		child_filters[parent_field] = parent
		children = frappe.get_all(doctype, filters=child_filters, fields=child_fields)

		for child in children:
			child_distributor = child.get("distributor") or child.name
			if child_distributor in visited:
				frappe.throw("Circular distributor relationship detected.")

			visited.add(child_distributor)
			child_level = depth + 1
			row = {
				"distributor": child_distributor,
				"level": child_level,
			}
			if child.get("leg_position"):
				row["leg_position"] = child.leg_position

			downline.append(row)
			queue.append((child_distributor, child_level))

	return downline


def get_parent_field(plan_type):
	if plan_type == BINARY:
		return "placement_parent"

	return "sponsor"


def get_binary_leg_summary(distributor):
	node = frappe.db.get_value(
		"Network Node",
		{"distributor": distributor},
		["left_count", "right_count"],
		as_dict=True,
	)
	if not node:
		return {"left_count": 0, "right_count": 0, "weak_leg": None}

	weak_leg = "Left" if node.left_count <= node.right_count else "Right"
	return {
		"left_count": node.left_count or 0,
		"right_count": node.right_count or 0,
		"weak_leg": weak_leg,
	}


def find_available_binary_position(start_distributor, preferred_leg=None):
	if preferred_leg and preferred_leg not in ("Left", "Right"):
		frappe.throw("Preferred leg must be Left or Right.")

	leg_order = [preferred_leg] if preferred_leg else ["Left", "Right"]
	if preferred_leg:
		leg_order.extend(leg for leg in ("Left", "Right") if leg != preferred_leg)

	queue = [start_distributor]
	visited = set()

	while queue:
		parent = queue.pop(0)
		if parent in visited:
			frappe.throw("Circular binary placement relationship detected.")

		visited.add(parent)
		children = frappe.get_all(
			"Network Node",
			filters={"parent_distributor": parent},
			fields=["distributor", "leg_position"],
		)
		children_by_leg = {child.leg_position: child.distributor for child in children}

		for leg in leg_order:
			if leg not in children_by_leg:
				return {"parent_distributor": parent, "leg_position": leg}

		for leg in ("Left", "Right"):
			if children_by_leg.get(leg):
				queue.append(children_by_leg[leg])

	return None
