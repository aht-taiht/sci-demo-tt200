from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_venue = fields.Boolean('Venue')
    is_insurance_company = fields.Boolean(string='Insurance Company', help='Check if the party is an Insurance Company')
    is_institution = fields.Boolean(string='Institution', help='Check if the party is a Medical Center')
    is_doctor = fields.Boolean(string='Health Professional', help='Check if the party is a health professional')
    is_patient = fields.Boolean(string='Is Patient', help='Check if the party is a patient')
    is_person = fields.Boolean(string='Person', help='Check if the party is a person.')
    is_pharmacy = fields.Boolean(string='Pharmacy', help='Check if the party is a Pharmacy')
    ref = fields.Char(size=256, string='Patient Social Security Number',
                      help='Patient Social Security Number or equivalent')
    contact_address_complete = fields.Char(store=True)
    birth_date = fields.Date('Birth date', tracking=True)
    year_of_birth = fields.Char('Year of birth', tracking=True)
    age = fields.Integer('Age', compute='set_age', tracking=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female'), ('transguy', 'Transguy'), ('transgirl', 'Transgirl'), ('other', 'Other')], string='Gender',
                              tracking=True)
    pass_port = fields.Char('Pass port', tracking=True)
    code_customer = fields.Char('Code customer', tracking=True)
    payment_ids = fields.One2many('account.payment', 'partner_id', string='Payments', tracking=True)
    source_id = fields.Many2one('utm.source', string='Source', tracking=True)
    career = fields.Char('Nghề nghiệp')
    pass_port_date = fields.Date('Pass port Date', tracking=True)
    pass_port_issue_by = fields.Char('Pass port Issue by', tracking=True)
    overseas_vietnamese = fields.Selection(
        [('no', 'No'), ('marketing', 'Marketing - Overseas Vietnamese'), ('branch', 'Branch - Overseas Vietnamese')],
        string='Overseas Vietnamese', default='no', tracking=True)
    allergy_history = fields.Text('Allergy history')
    district_id = fields.Many2one('res.country.district', string='District', tracking=True)
    customer_classification = fields.Selection(
        [('4', 'Đặc biệt'), ('3', 'Quan tâm hơn'), ('2', 'Quan tâm'), ('1', 'Bình thường')],
        string='Phân loại khách hàng', default='1')
    pass_port_address = fields.Char('Địa chỉ thường trú')
    customer_classification = fields.Selection(
        [('4', 'Đặc biệt'), ('3', 'Quan tâm hơn'), ('2', 'Quan tâm'), ('1', 'Bình thường')],
        string='Phân loại khách hàng', default='1')
    pass_port_address = fields.Char('Địa chỉ thường trú')
    marital_status = fields.Selection(
        [('single', 'Single'), ('in_love', 'In love'), ('engaged', 'Engaged'), ('married', 'Married'),
         ('divorce', 'Divorce'), ('other', 'Other')], string='Marital status', tracking=True)
    acc_facebook = fields.Char('Facebook Account', tracking=True)
    acc_zalo = fields.Char('Zalo Account', tracking=True)
    revenue_source = fields.Char('Revenue Source/Income', tracking=True)
    term_goals = fields.Char('Personal plan/Term goals', tracking=True)
    social_influence = fields.Char('Social Influence', tracking=True)
    behavior_on_the_internet = fields.Char('Behavior on the Internet', tracking=True)
    affected_by = fields.Selection(
        [('family', 'Family'), ('friend', 'Friend'), ('co_worker', 'Co-Worker'), ('community', 'Community'),
         ('electronic_media', 'Electronic media'), ('other', 'Other')], string='Affected by...', tracking=True)
    work_start_time = fields.Float('Work start time', tracking=True)
    work_end_time = fields.Float('Work end time', tracking=True)
    break_start_time = fields.Float('Break start time', tracking=True)
    break_end_time = fields.Float('Break end time', tracking=True)
    transport = fields.Selection(
        [('bicycle', 'Bicycle'), ('scooter', 'Scooter'), ('bus', 'Bus'), ('car', 'Car'), ('other', 'Other')],
        string='Transport', tracking=True)

    currency_id = fields.Many2one('res.currency', readonly=True)
    monetary = fields.Monetary()

    @api.depends('year_of_birth')
    def set_age(self):
        for rec in self:
            rec.age = 0
            if rec.year_of_birth and rec.year_of_birth.isdigit() is True:
                rec.age = fields.Datetime.now().year - int(rec.year_of_birth)

