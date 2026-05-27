// Copyright (c) 2026, prajil and contributors
frappe.ui.form.on("Payout Request", {

	refresh(frm) {
		if (frm.is_new()) {
			frm.set_value("request_date", frappe.datetime.get_today());
		}
		if (frm.doc.wallet) {
			frm.trigger("show_wallet_balance");
		}
	},

	distributor(frm) {
		if (!frm.doc.distributor) {
			frm.set_value("wallet", "");
			frm.set_df_property("request_amount", "description", "");
			return;
		}

		frm.set_query("wallet", () => {
			return { filters: { distributor: frm.doc.distributor } };
		});

		frappe.db.get_value("Wallet",
			{ distributor: frm.doc.distributor },
			["name", "current_balance"],
			(r) => {
				if (r && r.name) {
					frm.set_value("wallet", r.name);
					frm.__wallet_balance = flt(r.current_balance);
					frm.trigger("show_wallet_balance");
				} else {
					frappe.msgprint("No wallet found for this distributor.");
				}
			}
		);
	},

	wallet(frm) {
		frm.trigger("show_wallet_balance");
	},

	show_wallet_balance(frm) {
		if (!frm.doc.wallet) return;
		frappe.db.get_value("Wallet", frm.doc.wallet, "current_balance", (r) => {
			if (r) {
				frm.__wallet_balance = flt(r.current_balance);
				frm.set_df_property(
					"request_amount",
					"description",
					`<span style="color:green; font-weight:bold;">
						💰 Available Balance: ₹${frappe.utils.fmt_money(r.current_balance)}
					</span>`
				);
			}
		});
	},

	request_amount(frm) {
		frm.trigger("calculate_net_amount");
		frm.trigger("validate_balance");
	},

	charges(frm) {
		frm.trigger("calculate_net_amount");
	},

	calculate_net_amount(frm) {
		let request = flt(frm.doc.request_amount) || 0;
		let charges = flt(frm.doc.charges) || 0;
		frm.set_value("net_amount", request - charges);
	},

	validate_balance(frm) {
		if (!frm.doc.wallet || !frm.doc.request_amount) return;

		let available = frm.__wallet_balance || 0;
		let requested = flt(frm.doc.request_amount);

		if (requested > available) {
			// Show red warning below field
			frm.set_df_property(
				"request_amount",
				"description",
				`<span style="color:red; font-weight:bold;">
					⚠️ Insufficient Balance! Available: ₹${frappe.utils.fmt_money(available)}.
					Please reduce the withdrawal amount.
				</span>`
			);

			// Show popup
			frappe.msgprint({
				title: __("Insufficient Balance"),
				message: __(`You only have <b>₹${frappe.utils.fmt_money(available)}</b> in your wallet.<br><br>Please enter an amount less than or equal to your available balance.`),
				indicator: "red"
			});

			// Clear the field after short delay
			setTimeout(() => {
				frm.set_value("request_amount", 0);
			}, 500);

		} else {
			frm.set_df_property(
				"request_amount",
				"description",
				`<span style="color:green; font-weight:bold;">
					💰 Available Balance: ₹${frappe.utils.fmt_money(available)}
				</span>`
			);
		}
	},

	payout_method(frm) {
		frm.toggle_reqd("upi_id", frm.doc.payout_method === "UPI");
		frm.toggle_reqd("bank_account", frm.doc.payout_method === "Bank");
		frm.toggle_display("upi_id", frm.doc.payout_method === "UPI");
		frm.toggle_display("bank_account", frm.doc.payout_method === "Bank");
	},
});
