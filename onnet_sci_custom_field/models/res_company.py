from odoo import fields, api, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    code = fields.Char('Code company')
    enable_inter_company_transfer = fields.Boolean(string='Inter Company Transfer', copy=False)
    # destination_warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    apply_transfer_type = fields.Selection([('all', 'Delivery and Receipts'),
                                            ('incoming', 'Receipt'),
                                            ('outgoing', 'Delivery Order')], string='Apply On', default='all',
                                           help="Select the Picking type to apply the inter company transfer")
    message = fields.Text(string="Message")
    # region_picking_type = fields.Many2one('stock.picking.type', string='Bắc/Nam',
                                          # domain=[('company_id', '=', 1), ('code', '=', 'incoming')])
    location_shop = fields.Char('Địa chỉ gửi SMS')
    accreditation = fields.Text('Accreditation')
    approval_authority = fields.Text('Approval Authority')

# class ScriptSMS(models.Model):
#     _name = 'script.sms'
#
#     type = fields.Selection([('XNLH', 'Xác nhận lịch hẹn'), ('NHKHL1', 'Nhắc hẹn KH lần 1'),
#                              ('NHKHL2', 'Nhắc hẹn KH lần 2'), ('COKHLDV', 'Cảm ơn KH làm DV'),
#                              ('CMSN', 'SMS chúc mừng sinh nhật KH'),('CTKH', 'SMS chúc tết KH')],
#                             string='Tên SMS')
#     time_send = fields.Char('Thời gian gửi')
#     content = fields.Text('Nội dung')
#     company_id = fields.Many2one('res.company', string='Công ty')
#     note = fields.Text('Ghi chú')
