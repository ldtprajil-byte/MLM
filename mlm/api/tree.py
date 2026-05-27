import frappe


@frappe.whitelist()
def get_tree():

	nodes = frappe.get_all(
		"Network Node",
		fields=[
			"name",
			"distributor",
			"parent_distributor",
			"leg_position"
		]
	)

	return nodes