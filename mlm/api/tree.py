import frappe


@frappe.whitelist()
def get_tree():

    nodes = frappe.db.sql("""
        SELECT
            nn.name,
            nn.distributor,
            nn.parent_distributor,
            nn.leg_position,
            d.distributor_name
        FROM
            `tabNetwork Node` nn
        LEFT JOIN
            `tabDistributor` d ON d.name = nn.distributor
    """, as_dict=True)

    return nodes