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

				<!-- Stats Row - 4 expanded cards -->
				<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px;">
					<div style="background:#f8f9fa; border-radius:8px; padding:18px 20px;">
						<div style="font-size:14px; color:#333; margin-bottom:8px;">💰 Wallet</div>
						<div style="font-size:28px; font-weight:700; color:#2e7d32;">
							₹${frm.doc.wallet_balance || 0}
						</div>
					</div>
					<div style="background:#f8f9fa; border-radius:8px; padding:18px 20px;">
						<div style="font-size:14px; color:#333; margin-bottom:8px;">🏆 Rank</div>
						<div style="font-size:28px; font-weight:700; color:#1565c0;">
							<a onclick="frappe.set_route('List','Rank Log',{distributor:'${frm.doc.name}'}); return false;" href="#"
								style="color:#1565c0; text-decoration:none;">
								${frm.doc.current_rank || "STR"}
							</a>
						</div>
					</div>
					<div style="background:#f8f9fa; border-radius:8px; padding:18px 20px;">
						<div style="font-size:14px; color:#333; margin-bottom:8px;">👥 Left</div>
						<div style="font-size:28px; font-weight:700;">
							${frm.doc.left_count || 0}
						</div>
					</div>
					<div style="background:#f8f9fa; border-radius:8px; padding:18px 20px;">
						<div style="font-size:14px; color:#333; margin-bottom:8px;">👥 Right</div>
						<div style="font-size:28px; font-weight:700;">
							${frm.doc.right_count || 0}
						</div>
					</div>
				</div>

				<!-- Quick Links Row - 6 icons full width -->
				<div style="
					display:grid;
					grid-template-columns:repeat(6,1fr);
					gap:8px;
					border-top:1px solid #eee;
					padding-top:14px;
					padding-bottom:10px;
				">
					<a href="/dashboard?distributor=${frm.doc.name}" target="_blank"
						style="display:flex; flex-direction:column; align-items:center; gap:8px; padding:16px 8px; border-radius:8px; background:#f8f9fa; text-decoration:none; color:#333; text-align:center;">
						<span style="font-size:24px;">🏠</span>
						<span style="font-size:15px; font-weight:600;">Dashboard</span>
					</a>
					<a href="/wallet?distributor=${frm.doc.name}" target="_blank"
						style="display:flex; flex-direction:column; align-items:center; gap:8px; padding:16px 8px; border-radius:8px; background:#f8f9fa; text-decoration:none; color:#333; text-align:center;">
						<span style="font-size:24px;">💰</span>
						<span style="font-size:15px; font-weight:600;">Wallet</span>
					</a>
					<a href="/transactions?distributor=${frm.doc.name}" target="_blank"
						style="display:flex; flex-direction:column; align-items:center; gap:8px; padding:16px 8px; border-radius:8px; background:#f8f9fa; text-decoration:none; color:#333; text-align:center;">
						<span style="font-size:24px;">📄</span>
						<span style="font-size:15px; font-weight:600;">Transactions</span>
					</a>
					<a href="/genealogy?distributor=${frm.doc.name}" target="_blank"
						style="display:flex; flex-direction:column; align-items:center; gap:8px; padding:16px 8px; border-radius:8px; background:#f8f9fa; text-decoration:none; color:#333; text-align:center;">
						<span style="font-size:24px;">🌳</span>
						<span style="font-size:15px; font-weight:600;">Network Tree</span>
					</a>
					<a href="/payouts?distributor=${frm.doc.name}" target="_blank"
						style="display:flex; flex-direction:column; align-items:center; gap:8px; padding:16px 8px; border-radius:8px; background:#f8f9fa; text-decoration:none; color:#333; text-align:center;">
						<span style="font-size:24px;">🏦</span>
						<span style="font-size:15px; font-weight:600;">Payouts</span>
					</a>
					<a href="/commissions?distributor=${frm.doc.name}" target="_blank"
						style="display:flex; flex-direction:column; align-items:center; gap:8px; padding:16px 8px; border-radius:8px; background:#f8f9fa; text-decoration:none; color:#333; text-align:center;">
						<span style="font-size:24px;">🏅</span>
						<span style="font-size:15px; font-weight:600;">Commissions</span>
					</a>
				</div>

			</div>
		`);
	}
});