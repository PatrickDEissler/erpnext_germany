frappe.ui.form.on("Sales Invoice", {
	onload: function (frm) {
		frm.page.add_menu_item(__("Download XRechnung"), () => {
			window.open(
				"/api/method/erpnext_germany.xrechnung.download_xrechnung?invoice_id=" + frm.doc.name,
				"_blank"
			);
		});
	},
});
