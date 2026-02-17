import logging
from collections import defaultdict
from datetime import datetime

from lxml import etree

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class L10nAtZmReportHandler(models.AbstractModel):
    _name = 'l10n_at.zm.report.handler'
    _inherit = 'l10n_at.ec.sales.report.handler'
    _description = 'Austrian ZM (Zusammenfassende Meldung) XML Export Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['buttons'].append({
            'name': _('XML (ZM)'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'l10n_at_export_zm_to_xml',
            'file_export_type': _('XML'),
        })

    def l10n_at_export_zm_to_xml(self, options):
        """Generate BMF-compliant U13 XML for Austrian Zusammenfassende Meldung."""
        report = self.env['account.report'].browse(options['report_id'])
        company = report._get_sender_company_for_export(options)

        fastnr = company._get_l10n_at_fastnr_digits()
        if not fastnr or len(fastnr) != 9:
            raise UserError(_(
                "Please configure the Finanzamt-Steuernummer (FASTNR) on company '%(company)s' "
                "before exporting ZM XML.\n\n"
                "Go to Settings \u2192 Companies \u2192 %(company)s \u2192 General Information.",
                company=company.name,
            ))

        # Extract ZM entries from the report
        zm_entries = self._extract_zm_entries(report, options)

        if not zm_entries:
            raise UserError(_("No EC sales data found for the selected period."))

        # Build XML
        xml_content = self._build_zm_xml(fastnr, options, zm_entries)

        # Validate against XSD
        self._validate_zm_xml(xml_content)

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': xml_content,
            'file_type': 'xml',
        }

    def _extract_zm_entries(self, report, options):
        """Extract ZM entries from the EC sales report.

        Returns a list of dicts with keys: vat_number, amount, operation_type ('goods'/'triangular'/'services').
        """
        entries = []
        report_lines = report._get_lines(options)

        # Map column labels to indices
        colname_to_idx = {
            col['expression_label']: idx
            for idx, col in enumerate(options.get('columns', []))
        }

        balance_idx = colname_to_idx.get('balance')
        vat_idx = colname_to_idx.get('vat_number')
        country_idx = colname_to_idx.get('country_code')

        if balance_idx is None:
            raise UserError(_("Cannot find 'balance' column in report options."))

        for line in report_lines:
            # Skip total lines
            if line.get('class') == 'total' or not line.get('columns'):
                continue

            columns = line['columns']
            balance = columns[balance_idx].get('no_format', 0.0) if balance_idx < len(columns) else 0.0
            vat_number = columns[vat_idx].get('name', '') if vat_idx is not None and vat_idx < len(columns) else ''
            country_code = columns[country_idx].get('name', '') if country_idx is not None and country_idx < len(columns) else ''

            if not vat_number or not balance:
                continue

            # Determine operation type from the line markup
            line_id = line.get('id', '')
            if 'triangular' in line_id:
                operation_type = 'triangular'
            elif 'services' in line_id:
                operation_type = 'services'
            else:
                operation_type = 'goods'

            # Reconstruct full VAT number with country prefix
            full_vat = vat_number
            if country_code and not vat_number.startswith(country_code):
                full_vat = country_code + vat_number

            entries.append({
                'vat_number': full_vat,
                'amount': int(round(abs(balance))),
                'operation_type': operation_type,
            })

        return entries

    def _build_zm_xml(self, fastnr, options, zm_entries):
        """Build the ERKLAERUNGS_UEBERMITTLUNG XML for ZM (U13)."""
        now = datetime.now()
        paket_nr = self.env['ir.sequence'].next_by_code('l10n_at.uva.paket_nr') or '1'

        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        zrvon = date_from[:7]
        zrbis = date_to[:7]

        root = etree.Element('ERKLAERUNGS_UEBERMITTLUNG')

        # INFO_DATEN
        info = etree.SubElement(root, 'INFO_DATEN')
        etree.SubElement(info, 'ART_IDENTIFIKATIONSBEGRIFF').text = 'FASTNR'
        etree.SubElement(info, 'IDENTIFIKATIONSBEGRIFF').text = fastnr
        etree.SubElement(info, 'PAKET_NR').text = paket_nr
        datum = etree.SubElement(info, 'DATUM_ERSTELLUNG')
        datum.set('type', 'datum')
        datum.text = now.strftime('%Y-%m-%d')
        uhrzeit = etree.SubElement(info, 'UHRZEIT_ERSTELLUNG')
        uhrzeit.set('type', 'uhrzeit')
        uhrzeit.text = now.strftime('%H:%M:%S')
        etree.SubElement(info, 'ANZAHL_ERKLAERUNGEN').text = '1'

        # ERKLAERUNG
        erkl = etree.SubElement(root, 'ERKLAERUNG')
        erkl.set('art', 'U13')
        etree.SubElement(erkl, 'SATZNR').text = '1'

        # ALLGEMEINE_DATEN
        allg = etree.SubElement(erkl, 'ALLGEMEINE_DATEN')
        etree.SubElement(allg, 'ANBRINGEN').text = 'U13'
        zrvon_el = etree.SubElement(allg, 'ZRVON')
        zrvon_el.set('type', 'jahrmonat')
        zrvon_el.text = zrvon
        zrbis_el = etree.SubElement(allg, 'ZRBIS')
        zrbis_el.set('type', 'jahrmonat')
        zrbis_el.text = zrbis
        etree.SubElement(allg, 'FASTNR').text = fastnr

        # ZM entries
        for entry in zm_entries:
            zm = etree.SubElement(erkl, 'ZM')
            etree.SubElement(zm, 'UID_MS').text = entry['vat_number']
            sum_bgl = etree.SubElement(zm, 'SUM_BGL')
            sum_bgl.set('type', 'kz')
            sum_bgl.text = str(entry['amount'])

            if entry['operation_type'] == 'triangular':
                etree.SubElement(zm, 'DREIECK').text = 'J'
            elif entry['operation_type'] == 'services':
                etree.SubElement(zm, 'SOLEI').text = 'J'
            # goods = no DREIECK/SOLEI flag

        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8',
        )

    def _validate_zm_xml(self, xml_content):
        """Validate generated XML against the bundled ZM XSD schema."""
        import os
        xsd_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data',
            'BMF_XSD_Schema_Zusammenfassende_Meldung.xsd',
        )
        if not os.path.isfile(xsd_path):
            _logger.warning("ZM XSD schema file not found at %s, skipping validation.", xsd_path)
            return

        try:
            schema_doc = etree.parse(xsd_path)
            schema = etree.XMLSchema(schema_doc)
            doc = etree.fromstring(xml_content)
            if not schema.validate(doc):
                errors = '\n'.join(str(e) for e in schema.error_log)
                raise UserError(_(
                    "The generated XML does not conform to the BMF XSD schema:\n\n%(errors)s",
                    errors=errors,
                ))
        except etree.XMLSchemaError as e:
            _logger.error("ZM XSD validation failed: %s", e)
            raise UserError(_(
                "The generated XML does not conform to the BMF XSD schema:\n\n%(errors)s",
                errors=str(e),
            ))
