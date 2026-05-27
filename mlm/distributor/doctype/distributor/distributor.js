// Copyright (c) 2026, prajil and contributors
frappe.ui.form.on("Distributor", {

	refresh(frm) {

		if (frm.is_new()) return;

		// Share Registration Link
		frm.add_custom_button("Share Registration Link", () => {
			const referral_link =
				`${window.location.origin}/welcome/new?ref=${frm.doc.name}`;
			navigator.clipboard.writeText(referral_link);
			frappe.show_alert({
				message: "Joining link copied",
				indicator: "green"
			});
		});

		// Remove duplicate section
		$(".mlm-dashboard-links").remove();

		// Dashboard stats + Quick Links
		frm.dashboard.add_section(`
			<div class="mlm-dashboard-links" style="padding:10px;">

				<!-- Stats Row -->
				<div style="display:flex; gap:20px; flex-wrap:wrap; margin-bottom:12px;">
					<div>
						<div style="font-size:11px;color:#888;">💰 Wallet</div>
						<div style="font-size:16px;font-weight:700;color:#2e7d32;">
							₹${frm.doc.wallet_balance || 0}
						</div>
					</div>
					<div>
						<div style="font-size:11px;color:#888;">🏆 Rank</div>
						<div style="font-size:16px;font-weight:700;color:#1565c0;">
							<a onclick="frappe.set_route('List','Rank Log',{distributor:'${frm.doc.name}'}); return false;" href="#">
								${frm.doc.current_rank || "STR"}
							</a>
						</div>
					</div>
					<div>
						<div style="font-size:11px;color:#888;">👥 Left</div>
						<div style="font-size:16px;font-weight:700;">
							${frm.doc.left_count || 0}
						</div>
					</div>
					<div>
						<div style="font-size:11px;color:#888;">👥 Right</div>
						<div style="font-size:16px;font-weight:700;">
							${frm.doc.right_count || 0}
						</div>
					</div>
				</div>

				<!-- Quick Links Row -->
				<div style="display:flex; gap:20px; flex-wrap:wrap; border-top:1px solid #eee; padding-top:10px;">
					<a href="/dashboard?distributor=${frm.doc.name}" target="_blank">🏠 Dashboard</a>
					<a href="/wallet?distributor=${frm.doc.name}" target="_blank">
						💰 Wallet
					</a>
					<a href="/transactions?distributor=${frm.doc.name}" target="_blank">
						📄 Transactions
					</a>
					<a href="/genealogy?distributor=${frm.doc.name}" target="_blank">
						🌳 Network Tree
					</a>
					<a href="/payouts?distributor=${frm.doc.name}" target="_blank">
						🏦 Payouts
					</a>
					<a href="/commissions?distributor=${frm.doc.name}" target="_blank">
						🏅 Commissions
					</a>
				</div>

			</div>
		`);
	}
});
