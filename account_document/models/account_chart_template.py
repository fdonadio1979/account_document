##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    def _get_localizations(self):
        localizations = self.env['res.company']._fields[
            'localization']._description_selection(self.env)
        return localizations

    localization = fields.Selection(
        _get_localizations,
        'Localization',
        help='If you set the localization here, then when installing '
        'this chart, this localization will be set on company'
    )

    @api.multi
    def _load_template(
            self, company, code_digits=None, account_ref=None, taxes_ref=None):
        """
        Set localization to company when installing chart of account.
        """
        self.ensure_one()
        if not company.localization:
            company.localization = self and self.localization
        if company.localization:
            self.generate_receiptbooks(company)
        return super(AccountChartTemplate, self)._load_template(
            company, code_digits, account_ref, taxes_ref)

    @api.model
    def generate_receiptbooks(
            self, company):
        """
        Overwrite this function so that no journal is created on chart
        installation
        """
        receiptbook_data = self._prepare_all_receiptbook_data(company)
        for receiptbook_vals in receiptbook_data:
            self.check_created_receiptbooks(receiptbook_vals, company)
        return True

    @api.model
    def check_created_receiptbooks(self, receiptbook_vals, company):
        """
        This method used for checking new receipbooks already created or not.
        If not then create new receipbook.
        """
        receipbook = self.env['account.payment.receiptbook'].search([
            ('name', '=', receiptbook_vals['name']),
            ('company_id', '=', company.id)])
        if not receipbook:
            receipbook.create(receiptbook_vals)
        return True

    @api.model
    def _prepare_all_receiptbook_data(self, company):
        """
        This method can be inherited by different localizations
        """
        receiptbook_data = []
        partner_type_name_map = {
            'customer': _('%s Customer Receipts'),
            'supplier': _('%s Supplier Payments'),
        }
        sequence_types = {
            'automatic': _('Automatic'),
            'manual': _('Manual'),
        }
        # we use for sequences and for prefix
        sequences = {
            'automatic': 1,
            'manual': 2,
        }
        for sequence_type in ['automatic', 'manual']:
            # for internal_type in [
            #        'inbound_payment_voucher', 'outbound_payment_voucher']:
            for partner_type in ['supplier', 'customer']:
                document_type = self.env['account.document.type'].search([
                    ('internal_type', '=', '%s_payment' % partner_type)
                ], limit=1)
                if not document_type:
                    continue
                vals = {
                    'name': partner_type_name_map[partner_type] % (
                        sequence_types[sequence_type]),
                    'partner_type': partner_type,
                    'sequence_type': sequence_type,
                    'padding': 8,
                    'company_id': company.id,
                    'document_type_id': document_type.id,
                    'prefix': (
                        '%%0%sd-' % 4 % sequences[sequence_type]),
                    'sequence': sequences[sequence_type],
                }
                receiptbook_data.append(vals)
        return receiptbook_data

    @api.model
    def _prepare_all_journals(
            self, acc_template_ref, company, journals_dict=None):
        """
        We add use_documents or not depending on the context
        """
        journal_data = super(
            AccountChartTemplate, self)._prepare_all_journals(
            acc_template_ref, company, journals_dict)

        # if chart has localization, then we use documents by default
        if self.localization:
            for vals_journal in journal_data:
                if vals_journal['type'] == 'sale':
                    vals_journal['use_documents'] = self._context.get(
                        'sale_use_documents', True)
                if vals_journal['type'] == 'purchase':
                    vals_journal['use_documents'] = self._context.get(
                        'purchase_use_documents', True)
        return journal_data

    def load_for_current_company(self, sale_tax_rate, purchase_tax_rate):
        """ When we load a chart of account and set a default tax, add this tax
        to every product """
        res = super().load_for_current_company(
            sale_tax_rate, purchase_tax_rate)

        if request and request.session.uid:
            current_user = self.env['res.users'].browse(request.uid)
            company = current_user.company_id
        else:
            # fallback to company of current user, most likely __system__
            # (won't work well for multi-company)
            company = self.env.user.company_id

        prod_templates = self.env['product.template'].search([])
        if company.account_sale_tax_id:
            prod_templates.write({
                'taxes_id': [(4, company.account_sale_tax_id.id)],
            })
        if company.account_purchase_tax_id:
            prod_templates.write({
                'supplier_taxes_id': [(4, company.account_purchase_tax_id.id)],
            })
        return res
