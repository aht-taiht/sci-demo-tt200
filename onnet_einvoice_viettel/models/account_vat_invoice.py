# -*- coding: utf-8 -*-
import time
import logging
import requests
import re
from requests.auth import HTTPBasicAuth
from num2words import num2words
from bs4 import BeautifulSoup
import uuid

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.http import request, content_disposition

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
except AttributeError:
    # no pyopenssl support used / needed / available
    pass

_logger = logging.getLogger(__name__)


class AccountVATInvoice(models.Model):
    _inherit = "account.vat.invoice"

    viettel_branch_id = fields.Many2one('einvoice.viettel.branch', string="Viettel Branch")
    vsi_tin = fields.Char("Vat", related="viettel_branch_id.vsi_tin")
    vsi_template = fields.Char("Form", related="viettel_branch_id.vsi_template")
    vsi_template_type = fields.Char("Form Type", related="viettel_branch_id.vsi_template_type")
    vsi_series = fields.Char("Series", related="viettel_branch_id.vsi_series")

    origin_invoice = fields.Many2one("account.vat.invoice", "Origin e-invoice")
    is_adjustment_invoice = fields.Boolean(string="Is adjustment invoice?", default=False)
    adjustment_type = fields.Selection(
        [('1', _('Adjust money')),
         ('2', _('Adjust information'))],
        string="Adjustment type")
    adjustment_desc = fields.Char(
        "Adjustment Reference", help="Reference information, if any, attached to the invoice: written agreement between the buyer and seller on replacement and adjustment of the invoice.")
    adjustment_date = fields.Date(
        "Adjustment Date", help="Time when the written agreement arises between the buyer and the seller")

    fkey = fields.Char("Technical key", copy=False)
    pdf_file = fields.Many2one("ir.attachment", string="E-invoice PDF File", copy=False)
    pdf_draft_preview_file = fields.Many2one("ir.attachment", string="Draft E-invoice PDF File", copy=False)

    invoiceStatus = fields.Selection([
        ('0', "No e-invoice"),
        ('1', "Get e-invoice now"),
        ('2', "Get e-invoice later")
    ], string="E-invoice Status", copy=False)

    # Field in Invoice Viettel
    invoiceId = fields.Char("Viettel InvoiceID", copy=False)
    invoiceType = fields.Char('invoiceType')
    adjustmentType = fields.Char('adjustmentType')

    total = fields.Char('total')
    issueDate = fields.Char('issueDate')
    issueDateStr = fields.Char('issueDateStr')
    requestDate = fields.Char('requestDate')
    description = fields.Char('description')
    buyerCode = fields.Char('buyerCode')
    paymentStatus = fields.Char('paymentStatus')
    viewStatus = fields.Char('viewStatus')
    exchangeStatus = fields.Char('exchangeStatus')
    numOfExchange = fields.Char('numOfExchange')
    createTime = fields.Char('createTime')
    contractId = fields.Char('contractId')
    contractNo = fields.Char('contractNo')
    totalBeforeTax = fields.Char('totalBeforeTax')

    paymentMethod = fields.Char('paymentMethod')
    taxAmount = fields.Char('taxAmount')
    paymentTime = fields.Char('paymentTime')

    paymentStatusName = fields.Char('paymentStatusName')
    svcustomerName = fields.Char('Invoice export name')

    reservation_code = fields.Char(string="Secret number", copy=False)
    transaction_id = fields.Char(string="Transaction ID", copy=False)
    buyer_not_get_invoice = fields.Boolean(string="Buyer does not receive invoice", default=True)
    sinvoice_version = fields.Char(string="S-Invoice API Version", compute="_compute_sinvoice_api_version")

    @api.depends('viettel_branch_id', 'viettel_branch_id.version')
    def _compute_sinvoice_api_version(self):
        for rec in self:
            if rec.viettel_branch_id:
                rec.sinvoice_version = rec.viettel_branch_id.version
            else:
                rec.sinvoice_version = None

    # @api.depends('partner_id', 'partner_id.parent_id', 'buyer_not_get_invoice')
    # def _compute_street_partner(self):
    #     for inv in self:
    #         if self.buyer_not_get_invoice:
    #             inv.street_partner = None
    #         else:
    #             partner = inv.partner_id
    #             if not partner.is_company and partner.parent_id:
    #                 partner = partner.parent_id
    #             address = ''.join([partner.street, ', ', partner.street2 or '', ', ', partner.city or ''])
    #             inv.street_partner = address

    @api.depends('amount_total')
    def _sub_amount_total(self):
        for rec in self:
            rec.amount_total = rec.amount_tax + rec.amount_untaxed
            try:
                rec.amountinwords = num2words(
                    int(rec.amount_total), lang='vi_VN').capitalize() + " đồng chẵn."
            except NotImplementedError:
                rec.amountinwords = num2words(
                    int(rec.amount_total), lang='en').capitalize() + " VND."

    def download_file_pdf(self):
        self.check_config_einvoice()

        headers = {"Content-Type": "application/json"}
        api_url = self.viettel_branch_id.vsi_domain + '/InvoiceAPI/InvoiceUtilsWS/getInvoiceRepresentationFile'
        data = {
            "supplierTaxCode": self.vsi_tin,
            "invoiceNo": self.name,
            "templateCode": self.vsi_template,
            "fileType": "PDF"
        }
        _logger.info("Einvoice Download Request Data: %s", data)
        if self.viettel_branch_id.version == '1':
            result = requests.post(api_url, auth=HTTPBasicAuth(self.viettel_branch_id.vsi_username,
                                                               self.viettel_branch_id.vsi_password),
                                   json=data, headers=headers)
        else:
            cookies = self.generate_token()
            result = requests.post(api_url, json=data, headers=headers, cookies=cookies)
        # _logger.info("Einvoice Download Result: %s", result.text)
        result.raise_for_status()
        if not (result.json().get("errorCode") == '200'):
            ir_attachment_id = self.env['ir.attachment'].create({
                'name': result.json()["fileName"],
                'type': 'binary',
                'datas': result.json()["fileToBytes"],
                'store_fname': result.json()["fileName"],
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/x-pdf'
            })
            self.pdf_file = ir_attachment_id
        else:
            raise UserError("Download Invoice PDF Result: %s" % result.text)

    # Cancel Invoice
    def cancel_invoice_comfirm(self):
        if self.type != 'out_invoice':
            self.vsi_status = 'canceled'
            return
        self.check_config_einvoice()
        self.insert_log("Click Cancel Invoice")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "supplierTaxCode": self.vsi_tin,
            "templateCode": self.vsi_template,
            "invoiceNo": self.name,
            # "strIssueDate": int(self.date_invoice.timestamp() * 1000),
            "strIssueDate": self.date_invoice.strftime("%Y%m%d%H%M%S"),
            "additionalReferenceDesc": "hello",
            # "additionalReferenceDate": int(self.date_invoice.timestamp() * 1000)
            "additionalReferenceDate": fields.Datetime.now().strftime("%Y%m%d%H%M%S")
        }
        api_url = self.viettel_branch_id.vsi_domain + '/InvoiceAPI/InvoiceWS/cancelTransactionInvoice'
        if self.viettel_branch_id.version == '1':
            result = requests.post(
                api_url, auth=HTTPBasicAuth(self.viettel_branch_id.vsi_username, self.viettel_branch_id.vsi_password),
                data=data, headers=headers)
        else:
            cookies = self.generate_token()
            data.update({
                "strIssueDate": int(self.date_invoice.timestamp() * 1000),
                "additionalReferenceDate": int(self.date_invoice.timestamp() * 1000)
            })
            result = requests.post(api_url, data=data, headers=headers, cookies=cookies)
        try:
            if not result.json()["errorCode"]:
                self.vsi_status = 'canceled'
                if len(self.account_move_ids) > 0:
                    for account_move_id in self.account_move_ids:
                        account_move_id.vsi_status = 'canceled'
            else:
                raise UserError(
                    "Error when cancel invoice: " + result.text)
        except:
            raise UserError("Download Invoice Draft Preview PDF Result: %s" % result.text)

    def confirm_payment(self):
        self.check_config_einvoice()

        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Cookie": self.viettel_branch_id.vsi_token}
        if self.payment_type is not False:
            data = {
                "supplierTaxCode": self.vsi_tin,
                "templateCode": self.vsi_template,
                "invoiceNo": self.name,
                "buyerEmailAddress": self.email_partner,
                "paymentType": dict(self._fields['payment_type'].selection).get(self.payment_type),
                "paymentTypeName": dict(self._fields['payment_type'].selection).get(self.payment_type),
                "custGetInvoiceRight": True,
                "strIssueDate": self.date_invoice.strftime("%Y%m%d%H%M%S")
            }
        else:
            raise UserError("Choose payment type first")
        api_url = self.viettel_branch_id.vsi_domain + '/InvoiceAPI/InvoiceWS/updatePaymentStatus'
        result = requests.post(api_url, auth=HTTPBasicAuth(self.viettel_branch_id.vsi_username,
                               self.viettel_branch_id.vsi_password), params=data, headers=headers)
        _logger.info("Confirm Payment Result: %s", result.text)

    def unconfirm_payment(self):
        self.check_config_einvoice()

        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Cookie": self.viettel_branch_id.vsi_token}
        data = {
            "supplierTaxCode": self.vsi_tin,
            "invoiceNo": self.name,
            "strIssueDate": self.date_invoice.strftime("%Y%m%d%H%M%S")
        }
        api_url = self.viettel_branch_id.vsi_domain + '/InvoiceAPI/InvoiceWS/cancelPaymentStatus'
        result = requests.post(api_url, auth=HTTPBasicAuth(self.viettel_branch_id.vsi_username,
                               self.viettel_branch_id.vsi_password), params=data, headers=headers)
        _logger.debug("Cancel Payment Result: %s", result.text)

    def reset_einvoice_status(self):
        self.insert_log("Click Reset Status")
        self.write({
            'vsi_status': 'draft'
        })

    def resend_vnpt_email(self):
        self.insert_log("Click Download and Resend Invoice")
        # check xem da download pdf chua
        if len(self.pdf_file) == 0:
            self.download_file_pdf()

    def send_email_create_invoice(self):
        partner_id_array = []
        partner_ids = []
        if len(self.account_move_ids) > 0:
            for account_move_id in self.account_move_ids:
                partner_ids.append(
                    (4, account_move_id.invoice_user_id.partner_id.id))
                partner_id_array.append(account_move_id.invoice_user_id.partner_id.id)
                account_move_id.invoice_user_id.partner_id.id

        partner_name = self.partner_id.name
        if self.partner_id.company_type == 'employer' \
                and self.partner_id.customerName is not False:
            partner_name = self.partner_id.customerName

        # edit mail body
        body_html = "Kính gửi Quý khách hàng, <br/>" + self.company_id.name + \
            " xin trân trọng cảm ơn Quý khách hàng đã sử dụng dịch vụ "
        body_html += "của chúng tôi. <br/><br/>"
        body_html += self.company_id.name + \
            " vừa phát hành hóa đơn điện tử đến Quý khách. <br/><br/>"
        body_html += """Hóa đơn của Quý khách hàng có thông tin như sau: <br/><br/>
                • Họ tên người mua hàng: """

        body_html += partner_name + "<br/> "

        if self.VAT is not False:
            body_html += "• Mã Số Thuế: " + self.VAT + "<br/>"

        body_html += "• Hóa đơn số: "
        body_html += self.name + " thuộc mẫu số " + \
            self.vsi_template + " và serial " + self.vsi_series

        body_html += "<br/><br/>Mọi thắc mắc xin vui lòng liên hệ " + \
            self.company_id.name
        body_html += "<br/>ĐC: " + self.company_id.street
        body_html += """<br/>
                Điện thoại : """
        body_html += self.company_id.phone
        body_html += """<br/>
                Trân trọng.<br/>
        """
        create_values = {
            'body_html': body_html,
            'email_from': self.company_id.email,
            'subject': _("Phát hành hóa đơn điện tử %s ") % self.name,
            'recipient_ids': partner_ids,
            'attachment_ids': [(6, 0, [self.pdf_file.id])]
        }
        self.with_context({'force_write': True}).message_post(
            body=create_values['body_html'],
            subject=create_values['subject'],
            message_type='email',
            subtype_xmlid=None,
            partner_ids=partner_id_array,
            attachment_ids=[self.pdf_file.id],
            add_sign=True,
            model_description=False,
            mail_auto_delete=False
        )

    def insert_log(self, message):
        self.message_post(
            body=message,
            message_type='comment',
            author_id=self.env.user.partner_id.id if self.env.user.partner_id else None,
            subtype_xmlid='mail.mt_comment',
        )

    def get_seller_code(self):
        sellerCode = '11111111'
        for account_move_id in self.account_move_ids:
            seller = account_move_id.invoice_user_id
            sellerCode = seller.update_to_einvoice(self.viettel_branch_id)
            break
        return sellerCode

    def send_einvoice(self):

        self.insert_log("Click Issue Invoice")
        self.with_context(force_write=True)
        # Check already created einvoice
        if self.vsi_status == 'created':
            raise UserError("Invoices have been created e-invoice")
        elif self.vsi_status == 'creating':
            raise UserError("Invoices are being created e-invoice")
        self.vsi_status = "creating"
        self._cr.commit()
        # Check config
        self.check_config_einvoice()
        data = self.prepare_invoice_data()
        self.fkey = str(uuid.uuid4())
        data['generalInvoiceInfo']['transactionUuid'] = self.fkey
        headers = {
            "Content-Type": "application/json",
        }
        api_url = self.viettel_branch_id.vsi_domain + '/InvoiceAPI/InvoiceWS/createInvoice/' + self.viettel_branch_id.vsi_tin
        # _logger.info("Einvoice Content : %s", data)
        self.insert_log("Start connecting S-Invoice and issue e-invoices")
        if self.viettel_branch_id.version == '1':
            result = requests.post(
                api_url, auth=(self.viettel_branch_id.vsi_username, self.viettel_branch_id.vsi_password), json=data,
                headers=headers)
        else:
            cookies = self.generate_token()
            result = requests.post(
                api_url, json=data, headers=headers, cookies=cookies)
        _logger.info("Einvoice Result : %s", result.text)
        self.insert_log("End the S-Invoice connection. Result: " + result.text)
        json_result = result.json()
        if not json_result.get("errorCode", True) and "result" in json_result:
            self.vsi_status = "created"
            self.name = json_result["result"]["invoiceNo"]
            self.reservation_code = json_result["result"]["reservationCode"]
            self.transaction_id = json_result["result"]["transactionID"]
            try:
                time.sleep(2)
                # self.confirm_payment()
                time.sleep(2)
                self.download_file_pdf()
                time.sleep(2)
            except:
                pass

            if len(self.account_move_ids) > 0:
                for account_move_id in self.account_move_ids:
                    account_move_id.vsi_template = self.vsi_template
                    account_move_id.vsi_series = self.vsi_series
                    account_move_id.vsi_number = json_result["result"]["invoiceNo"]
                    account_move_id.vat_invoice_date = self.date_invoice
                    account_move_id.vsi_status = 'created'

                self.insert_log(" Updated invoice number successfully ")
            self.vsi_status = "created"
        else:
            raise UserError(
                "Error when issuing invoice " + result.text)

    def adjust_einvoice(self):
        self.check_config_einvoice()
        self.insert_log("Click Issue Adjustment Invoice")
        generalInvoiceInfo = {
            "invoiceType": self.vsi_template_type,
            "templateCode": self.vsi_template,
            "invoiceSeries": self.vsi_series or "",
            "currencyCode": self.currency_id.name,
            "exchangeRate": round(self.exchange_rate, 2),
            "adjustmentType": 5,
            "adjustmentInvoiceType": self.adjustment_type,
            "originalInvoiceId": self.origin_invoice.name,
            "paymentStatus": False,
            "cusGetInvoiceRight": True,
            "transactionUuid": self.transaction_id or "",
            "originalInvoiceIssueDate": int(self.date_invoice.timestamp() * 1000),
            "additionalReferenceDesc": self.adjustment_desc or dict(self._fields['adjustment_type'].selection).get(self.adjustment_type) or "",
            "additionalReferenceDate": int(fields.Datetime.to_datetime(self.adjustment_date).timestamp() * 1000) if self.adjustment_date else int(fields.Datetime.now().timestamp() * 100)
        }
        payments = [{
            "paymentMethod": self.payment_type or "",
            "paymentMethodName": dict(self._fields['payment_type'].selection).get(self.payment_type) or ""
        }]
        itemInfo = []
        line_no = 1
        for invoice_line in self.invoice_line_ids:
            unit_name = invoice_line.invoice_uom_id if invoice_line.invoice_uom_id else ''
            itemInfo.append({
                "lineNumber": line_no,
                "itemName": invoice_line.name,
                "itemCode": invoice_line.product_id.default_code or "",
                "unitName": unit_name,
                "quantity": invoice_line.quantity,
                "unitPrice": invoice_line.price_unit,
                "itemTotalAmountWithoutTax": invoice_line.price_subtotal,
                'taxPercentage': invoice_line.vat_rate or 0,
                "taxAmount": int(invoice_line.vat_amount),
                "itemTotalAmountWithTax": int(invoice_line.price_total),
                "isIncreaseItem": invoice_line.is_increase_adj,
                "adjustmentTaxAmount": invoice_line.vat_amount
            })
            line_no += 1
        summarizeInfo = self.get_summarize_info()
        summarizeInfo['isTotalAmountPos'] = True
        summarizeInfo['isTotalTaxAmountPos'] = True
        summarizeInfo['isTotalAmtWithoutTaxPos'] = True
        summarizeInfo['isDiscountAmtPos'] = True

        data = {
            "generalInvoiceInfo": generalInvoiceInfo,
            "buyerInfo": self.get_buyer_info(),
            "sellerInfo": self.get_seller_info(),
            "payments": payments,
            "itemInfo": itemInfo,
            "summarizeInfo": summarizeInfo,
            "taxBreakdowns": self.get_tax_breakdown()
        }
        _logger.info("Adjust Invoice Data: %s", data)

        # Connect api
        self.check_config_einvoice()
        self.fkey = str(uuid.uuid4())
        data['generalInvoiceInfo']['transactionUuid'] = self.fkey
        headers = {
            "Content-Type": "application/json",
        }
        api_url = self.viettel_branch_id.vsi_domain + '/InvoiceAPI/InvoiceWS/createInvoice/' + self.viettel_branch_id.vsi_tin
        if self.viettel_branch_id.version == '1':
            result = requests.post(api_url, auth=(self.viettel_branch_id.vsi_username,
                                   self.viettel_branch_id.vsi_password), json=data, headers=headers)
        else:
            cookies = self.generate_token()
            result = requests.post(api_url, json=data, headers=headers, cookies=cookies)

        _logger.info("Adjust Invoice Result: %s", result.text)
        if not result.json()["errorCode"]:
            self.name = result.json()["result"]["invoiceNo"]
            self.reservation_code = result.json()["result"]["reservationCode"]
            self.transaction_id = result.json()["result"]["transactionID"]
            self.vsi_status = "created"
            try:
                time.sleep(2)
                # self.confirmPayment()
                time.sleep(2)
                self.download_file_pdf()
                time.sleep(2)
            except:
                pass
        else:
            raise UserError(
                "Invoice issuance failed: %s" % result.text)

    def unlink(self):
        for record in self:
            if record.vsi_status == 'created' and not self.env.context.get('force_write', False):
                raise UserError(_('This invoice ' + record.name +
                                  '(' + str(record.id) + ')' + ' is created, can not delete'))
        return super(AccountVATInvoice, self).unlink()

    def task_check_created_einvoice(self):
        # Check config
        einvoices = self.env['account.vat.invoice'].sudo().search([('vsi_status', '=', 'creating')])

        for einvoice in einvoices:
            if len(einvoice.viettel_branch_id) == 0:
                logging.info("Invoice issuance configuration has not been selected")
                continue

            xmlformdata = """<?xml version="1.0" encoding="utf-8"?>
        <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns:xsd="http://www.w3.org/2001/XMLSchema"
         xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
            <soap12:Body>
                <listInvByCusFkey xmlns="http://tempuri.org/">"""
            xmlformdata += "<key>" + einvoice.fkey + \
                           "</key><fromDate></fromDate><toDate></toDate><userName>" + einvoice.viettel_branch_id.vsi_username
            xmlformdata += "</userName><userPass>" + einvoice.viettel_branch_id.vsi_password + """</userPass>
                                    </listInvByCusFkey>
                            </soap12:Body>
                        </soap12:Envelope>
                        """
            headers = {"Content-Type": "application/soap+xml; charset=utf-8",
                       "Cookie": self.viettel_branch_id.vsi_token}

            api_url = einvoice.viettel_branch_id.portal_service_domain
            result = requests.post(
                api_url, data=xmlformdata, headers=headers)
            result_soup = BeautifulSoup(result.content.decode("utf- 8"), 'xml')
            readable_content = result_soup.listInvByCusFkeyResult.text
            if 'ERR' not in readable_content and BeautifulSoup(readable_content, 'xml').Data.Item != None:
                result_content_soup = BeautifulSoup(readable_content, 'xml').Data.Item
                invoice_no = result_content_soup.invNum.text
                einvoice.vsi_status = 'created'
                einvoice.name = invoice_no
                if len(einvoice.account_move_ids) > 0:
                    for account_move_id in einvoice.account_move_ids:
                        account_move_id.vsi_template = einvoice.vsi_template
                        account_move_id.vsi_series = einvoice.vsi_series
                        account_move_id.vsi_number = invoice_no
                        account_move_id.einvoice_date = einvoice.date_invoice
                        account_move_id.vsi_status = 'created'
                self._cr.commit()
            else:
                logging.info(
                    "Error when checking invoice " + str(einvoice.id) + " Error" + readable_content)

    def get_buyer_info(self):
        if not self.street_partner:
            raise UserError(_("Missing Address."))

        bank = self.partner_id.bank_ids.filtered(lambda b: b.einvoice_bank == True)
        cus_bank_no = bank.acc_number if bank else ''
        cus_bank_name = bank.bank_id.name if bank else ''
        buyer_legal_name = ''
        buyer_name = ''
        if self.partner_id.is_company:
            buyer_legal_name = self.partner_id.name
        if self.buyer_name:
            buyer_name = self.buyer_name
        if not self.partner_id.is_company and self.partner_id.parent_id:
            buyer_legal_name = self.partner_id.parent_id.name
        if not buyer_legal_name:
            buyer_legal_name = self.partner_id.name
        buyer_info = {
            "buyerName": buyer_name,
            "buyerTaxCode": self.vat_partner or "",
            "buyerAddressLine": self.street_partner or '',
            "buyerLegalName": buyer_legal_name,
            "buyerEmail": self.email_partner or "",
            "buyerBankName": cus_bank_name,
            "buyerBankAccount": cus_bank_no
        }
        if self.phone_partner:
            buyer_info["buyerPhoneNumber"] = re.sub(r"[^0-9]", "", self.phone_partner)
        if self.buyer_not_get_invoice and self.viettel_branch_id.version == '2':
            buyer_info.update({
                # "buyerAddressLine": "",
                "buyerNotGetInvoice": 1,
            })
        return buyer_info

    def get_seller_info(self):
        # "sellerInfo":{
        #     "sellerLegalName":"Đặng thị thanh tâm",
        #     "sellerTaxCode":"0100109106-501",
        #     "sellerAddressLine":"test",
        #     "sellerPhoneNumber":"0123456789",
        #     "sellerEmail":"PerformanceTest1@viettel.com.vn",
        #     "sellerBankName":"vtbank",
        #     "sellerBankAccount":"23423424"
        # },
        seller_info = {}
        return seller_info

    def get_item_info(self):
        item_info = []
        line_no = 1
        for invoice_line in self.invoice_line_ids:
            unit_name = invoice_line.invoice_uom_id if invoice_line.invoice_uom_id else ''
            item_data = {
                "lineNumber": line_no,
                "itemName": invoice_line.name,
                "itemCode": invoice_line.product_id.default_code or "",
                "unitName": unit_name,
                "quantity": invoice_line.quantity,
                "unitPrice": abs(int(invoice_line.price_unit)),
                "itemTotalAmountWithoutTax": abs(int(invoice_line.price_subtotal)),
                'taxPercentage': invoice_line.vat_rate or 0,
                "taxAmount": abs(int(invoice_line.vat_amount)),
                "itemTotalAmountWithTax": abs(int(invoice_line.price_total))
            }
            if invoice_line.price_total < 0:
                item_data.update({
                    "selection": 3,
                })
            item_info.append(item_data)
            line_no += 1
        return item_info

    def check_config_einvoice(self):
        if self.type == 'out_invoice':
            if not self.viettel_branch_id:
                raise UserError("Viettel Branch configuration has not been selected")
            if self.viettel_branch_id and self.viettel_branch_id.version == '2' and not self.viettel_branch_id.vsi_token:
                raise UserError("No Token provided for this Company Branch. Please check config again")

    def get_summarize_info(self):
        return {
            "sumOfTotalLineAmountWithoutTax": self.amount_untaxed,
            "totalAmountWithoutTax": self.amount_untaxed,
            "totalTaxAmount": self.amount_tax,
            "totalAmountWithTax": self.amount_total,
            "totalAmountWithTaxInWords": self.amountinwords,
            "taxPercentage": self.taxRate if self.taxRate != '/' else '-1',
            "discountAmount": 0
        }

    def get_tax_breakdown(self):
        return [{
            "taxPercentage": self.taxRate if self.taxRate != '/' else '-1',
            "taxableAmount": self.amount_untaxed,
            "taxAmount": self.amount_tax
        }]

    def prepare_invoice_data(self):
        general_invoice_info = {
            "invoiceType": self.viettel_branch_id.vsi_template_type,
            "templateCode": self.viettel_branch_id.vsi_template,
            "invoiceSeries": self.viettel_branch_id.vsi_series or "",
            "currencyCode": self.currency_id.name,
            "exchangeRate": round(self.exchange_rate, 2),
            "adjustmentType": 1,
            "paymentStatus": True,
            "invoiceIssuedDate": int(self.date_invoice.timestamp() * 1000),
            "paymentTypeName": dict(self._fields['payment_type'].selection).get(self.payment_type),
        }
        #  Trong trường hợp sellerTaxCode không được truyền sang
        #  thì toàn bộ dữ liệu người bán hàng sẽ được lấy từ
        #  dữ liệu khai báo hệ thống hóa đơn điện tử
        #  được gán theo user đang xử dụng xác thực.
        payments = [
            {
                "paymentMethodName": dict(self._fields['payment_type'].selection).get(self.payment_type)
            }
        ]
        summarize_info = self.get_summarize_info()

        data = {
            "generalInvoiceInfo": general_invoice_info,
            "buyerInfo": self.get_buyer_info(),
            "sellerInfo": self.get_seller_info(),
            "payments": payments,
            "itemInfo": self.get_item_info(),
            "summarizeInfo": summarize_info,
            "taxBreakdowns": self.get_tax_breakdown()
        }
        return data

    def get_draft_preview(self):
        self.check_config_einvoice()
        data = self.prepare_invoice_data()
        _logger.info("Request: %s", data)
        headers = {
            "Content-Type": "application/json"
        }
        api_url = self.viettel_branch_id.vsi_domain + \
            '/InvoiceAPI/InvoiceUtilsWS/createInvoiceDraftPreview/' + self.viettel_branch_id.vsi_tin
        if self.viettel_branch_id.version == '1':
            result = requests.post(
                api_url, auth=(self.viettel_branch_id.vsi_username, self.viettel_branch_id.vsi_password), json=data,
                headers=headers)
        else:
            cookies = self.generate_token()
            result = requests.post(api_url, json=data, headers=headers, cookies=cookies)
        try:
            result.raise_for_status()
            if not result.json()["errorCode"]:
                ir_attachment_id = self.env['ir.attachment'].create({
                    'name': result.json()["fileName"],
                    'type': 'binary',
                    'datas': result.json()["fileToBytes"],
                    'store_fname': result.json()["fileName"],
                    'res_model': self._name,
                    'res_id': self.id,
                    'mimetype': 'application/x-pdf'
                })
                if self.pdf_draft_preview_file:
                    self.pdf_draft_preview_file.unlink()
                    self.pdf_draft_preview_file = ir_attachment_id
                else:
                    self.pdf_draft_preview_file = ir_attachment_id
                action = {
                    'type': 'ir.actions.act_url',
                    'url': "web/content/?model=ir.attachment&id=" + str(
                        self.pdf_draft_preview_file.id) + "&filename_field=name&field=datas&download=true&name=" + self.pdf_draft_preview_file.name,
                    'target': 'self'
                }
                return action
            else:
                raise UserError("Download Invoice Draft Preview PDF Result: %s" % result.text)
        except Exception:
            raise UserError("Download Invoice Draft Preview PDF Result: %s" % result.text)

    def generate_token(self):
        access_token = self.viettel_branch_id.action_get_token()
        if access_token:
            return {'access_token': access_token}
        else:
            raise UserError("Cannot generate access token. This could be due to wrong configuration in company branch.")

    def update_einvoice_number(self):
        if not self.name:
            self.check_config_einvoice()
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            api_url = self.viettel_branch_id.vsi_domain + '/InvoiceAPI/InvoiceWS/searchInvoiceByTransactionUuid'
            data = {
                'supplierTaxCode': self.vsi_tin,
                'transactionUuid': self.fkey,
            }
            if self.viettel_branch_id.version == '1':
                result = requests.post(
                    api_url,
                    auth=HTTPBasicAuth(self.viettel_branch_id.vsi_username, self.viettel_branch_id.vsi_password),
                    data=data, headers=headers)
            else:
                cookies = self.generate_token()
                result = requests.post(api_url, data=data, headers=headers, cookies=cookies)
            try:
                if not result.json()["errorCode"]:
                    invoice_data = result.json()['result'][0]
                    self.name = invoice_data['invoiceNo']
                else:
                    raise UserError(
                        "Error while updating invoice " + result.text)
            except:
                raise UserError("Update invoice data: %s" % result.text)
        if self.name:
            self.download_file_pdf()
