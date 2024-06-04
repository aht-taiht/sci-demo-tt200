from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ModelSyncedMixin(models.AbstractModel):

    _name = 'synced.mixin'

    synced = fields.Boolean(string= _('Synced'), default=False)
    com_id = fields.Integer(string=_("Community ID"))

    def write(self, vals):
        synced = False
        if not self.env.user.has_group('odoo_restful.group_sync_api'):
            for rec in self:
                if rec.synced:
                    synced = True
                    break
            if synced:
                raise UserError(_('Bản ghi được đồng bộ lên từ community, nên không được phép sửa'))

        return super(ModelSyncedMixin, self).write(vals)

    def unlink(self):
        synced = False
        if not self.env.user.has_group('odoo_restful.group_sync_api'):
            for rec in self:
                if rec.synced:
                    synced = True
                    break
            if synced:
                raise UserError(_('Bản ghi được đồng bộ lên từ community, nên không được phép xóa'))

        return super(ModelSyncedMixin, self).unlink()

class Account(models.Model):

    _name = "account.account"
    _inherit = ['account.account', 'synced.mixin']

class ProductCategory(models.Model):

    _name = "product.category"
    _inherit = ['product.category', 'synced.mixin']

class UomCategory(models.Model):

    _name = "uom.category"
    _inherit = ['uom.category', 'synced.mixin']

class Uom(models.Model):

    _name = "uom.uom"
    _inherit = ['uom.uom', 'synced.mixin']

class ProductAttribute(models.Model):

    _name = "product.attribute"
    _inherit = ['product.attribute', 'synced.mixin']

class ProductAttributeValue(models.Model):

    _name = "product.attribute.value"
    _inherit = ['product.attribute.value', 'synced.mixin']

class ProductAttributeLine(models.Model):

    _name = "product.template.attribute.line"
    _inherit = ['product.template.attribute.line', 'synced.mixin']

class ProductTemplateAttributeValue(models.Model):

    _name = "product.template.attribute.value"
    _inherit = ['product.template.attribute.value', 'synced.mixin']

class ProductTemplate(models.Model):

    _name = "product.template"
    _inherit = ['product.template', 'synced.mixin']

class ProductProduct(models.Model):

    _name = "product.product"
    _inherit = ['product.product', 'synced.mixin']

class PriceList(models.Model):

    _name = "product.pricelist"
    _inherit = ['product.pricelist', 'synced.mixin']

class ResCurrency(models.Model):

    _name = "res.currency"
    _inherit = ['res.currency', 'synced.mixin']

# class ProjectProject(models.Model):

    # _name = "project.project"
    # _inherit = ['project.project', 'synced.mixin']

class ResPartner(models.Model):

    _name = "res.partner"
    _inherit = ['res.partner', 'synced.mixin']

class ResBank(models.Model):

    _name = "res.bank"
    _inherit = ['res.bank', 'synced.mixin']

class ResPartnerBank(models.Model):

    _name = "res.partner.bank"
    _inherit = ['res.partner.bank', 'synced.mixin']

class ResPartnerCategory(models.Model):

    _name = "res.partner.category"
    _inherit = ['res.partner.category', 'synced.mixin']

class ResCompany(models.Model):

    _name = "res.company"
    _inherit = ['res.company', 'synced.mixin']

class AccountJournal(models.Model):

    _name = "account.journal"
    _inherit = ['account.journal', 'synced.mixin']

class ResCountry(models.Model):

    _name = "res.country"
    _inherit = ['res.country', 'synced.mixin']

class ResCountryState(models.Model):

    _name = "res.country.state"
    _inherit = ['res.country.state', 'synced.mixin']

class ResUsers(models.Model):

    _name = "res.users"
    _inherit = ['res.users', 'synced.mixin']

class AccountMove(models.Model):

    _name = "account.move"
    _inherit = ['account.move', 'synced.mixin']

class AccountMoveLine(models.Model):

    _name = "account.move.line"
    _inherit = ['account.move.line', 'synced.mixin']

class AccountTax(models.Model):

    _name = "account.tax"
    _inherit = ['account.tax', 'synced.mixin']

class AccountPaymentTerm(models.Model):

    _name = "account.payment.term"
    _inherit = ['account.payment.term', 'synced.mixin']

class AccountAnalyticAccount(models.Model):

    _name = "account.analytic.account"
    _inherit = ['account.analytic.account', 'synced.mixin']

class AccountAnalyticLine(models.Model):

    _name = "account.analytic.line"
    _inherit = ['account.analytic.line', 'synced.mixin']
