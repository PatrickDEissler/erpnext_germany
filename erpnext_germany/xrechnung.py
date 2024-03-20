from decimal import Decimal

import frappe
from drafthorse.models.accounting import ApplicableTradeTax
from drafthorse.models.document import Document
from drafthorse.models.party import TaxRegistration
from drafthorse.models.tradelines import LineItem
from frappe.utils.data import flt


@frappe.whitelist()
def download_xrechnung(invoice_id: str):
	invoice = frappe.get_doc("Sales Invoice", invoice_id)
	invoice.check_permission("read")

	seller_address = frappe.get_doc("Address", invoice.company_address)
	customer_address = frappe.get_doc("Address", invoice.customer_address)
	company = frappe.get_doc("Company", invoice.company)

	frappe.local.response.filename = f"{invoice_id}.xml"
	frappe.local.response.filecontent = get_xml(
		invoice, company, seller_address, customer_address
	)
	frappe.local.response.type = "download"


def get_xml(invoice, company, seller_address, customer_address):
	doc = Document()
	doc.context.guideline_parameter.id = (
		"urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended"
	)
	doc.header.id = invoice.name
	doc.header.type_code = "380"  # Handelsrechnungen
	doc.header.name = "RECHNUNG"
	doc.header.issue_date_time = invoice.posting_date
	doc.header.languages.add(invoice.language)

	doc.trade.settlement.payee.name = invoice.customer_name
	doc.trade.settlement.invoicee.name = invoice.customer_name

	doc.trade.settlement.currency_code = invoice.currency
	doc.trade.settlement.payment_means.type_code = (
		"ZZZ"  # TODO: implement type codes as custom field
	)

	doc.trade.agreement.seller.name = invoice.company
	if invoice.company_tax_id:
		doc.trade.agreement.seller.tax_registrations.add(
			TaxRegistration(
				id=("VA", invoice.company_tax_id),
			)
		)

	if company.phone_no:
		doc.trade.agreement.seller.contact.telephone.number = company.phone_no
	if company.email:
		doc.trade.agreement.seller.contact.email.address = company.email

	doc.trade.agreement.seller.address.line_one = seller_address.address_line1
	doc.trade.agreement.seller.address.line_two = seller_address.address_line2
	doc.trade.agreement.seller.address.postcode = seller_address.pincode
	doc.trade.agreement.seller.address.city_name = seller_address.city
	doc.trade.agreement.seller.address.country_id = frappe.db.get_value(
		"Country", seller_address.country, "code"
	).upper()

	doc.trade.agreement.buyer.name = invoice.customer_name
	doc.trade.agreement.buyer_reference = invoice.po_no or "unknown"
	doc.trade.agreement.buyer.address.line_one = customer_address.address_line1
	doc.trade.agreement.buyer.address.line_two = customer_address.address_line2
	doc.trade.agreement.buyer.address.postcode = customer_address.pincode
	doc.trade.agreement.buyer.address.city_name = customer_address.city
	doc.trade.agreement.buyer.address.country_id = frappe.db.get_value(
		"Country", customer_address.country, "code"
	).upper()

	for item in invoice.items:
		li = LineItem()
		li.document.line_id = str(item.idx)
		li.product.name = item.item_name
		li.agreement.net.amount = flt(item.net_amount, item.precision("net_amount"))
		li.delivery.billed_quantity = (
			flt(item.qty, item.precision("qty")),
			"C62",  # TODO: implement UOM code as custom field
		)
		li.settlement.trade_tax.type_code = "VAT"
		li.settlement.trade_tax.category_code = (
			"S"  # TODO: implement VAT category code as custom field
		)
		li.settlement.trade_tax.rate_applicable_percent = Decimal("19.00")
		li.settlement.monetary_summation.total_amount = flt(
			item.amount, item.precision("amount")
		)
		doc.trade.items.add(li)

	trade_tax = ApplicableTradeTax()
	trade_tax.calculated_amount = invoice.total_taxes_and_charges
	trade_tax.basis_amount = invoice.net_total
	trade_tax.type_code = "VAT"
	trade_tax.category_code = "S"
	trade_tax.rate_applicable_percent = Decimal("19.00")
	doc.trade.settlement.trade_tax.add(trade_tax)

	doc.trade.settlement.monetary_summation.line_total = invoice.total
	doc.trade.settlement.monetary_summation.charge_total = Decimal("0.00")
	doc.trade.settlement.monetary_summation.allowance_total = invoice.discount_amount
	doc.trade.settlement.monetary_summation.tax_basis_total = invoice.net_total
	doc.trade.settlement.monetary_summation.tax_total = invoice.total_taxes_and_charges
	doc.trade.settlement.monetary_summation.grand_total = invoice.grand_total
	doc.trade.settlement.monetary_summation.due_amount = invoice.outstanding_amount

	return doc.serialize(schema="FACTUR-X_EXTENDED")
