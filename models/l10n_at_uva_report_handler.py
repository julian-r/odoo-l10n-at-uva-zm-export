import logging
from datetime import datetime

from lxml import etree

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Mapping from account.report.line code to XML KZ element name.
# The XML structure groups KZ fields into sections; we map flat codes here
# and handle the nesting in the XML builder.

# Section: LIEFERUNGEN_LEISTUNGEN_EIGENVERBRAUCH (top-level)
_LLE_TOP = ['000', '001', '021']

# Section: STEUERFREI
_STEUERFREI = ['011', '012', '015', '017', '018', '019', '016', '020']

# Section: VERSTEUERT (tax base amounts only — the XSD uses Bemessungsgrundlage here)
_VERSTEUERT = ['022', '029', '006', '037', '052', '007']

# Section: VERSTEUERT additional tax liability fields (direct amounts, not base/tax split)
_VERSTEUERT_EXTRA = ['056', '057', '048', '044', '032']

# Section: INNERGEMEINSCHAFTLICHE_ERWERBE (top-level)
_IGE_TOP = ['070', '071']

# Section: VERSTEUERT_IGE (tax base amounts)
_VERSTEUERT_IGE = ['072', '073', '008', '088']

# Section: VERSTEUERT_IGE non-taxable
_IGE_NONTAX = ['076', '077']

# Section: VORSTEUER
_VORSTEUER = ['060', '061', '083', '065', '066', '082', '087', '089', '064', '062', '063', '067', '090']

# KZ fields that allow negative values (kzvorz type in XSD)
_ALLOW_NEGATIVE = {'063', '067', '090'}

# KZ fields that allow zero (kznull type in XSD)
_ALLOW_ZERO = {'000', '070'}

# Report line codes that use _base suffix for Bemessungsgrundlage
_BASE_SUFFIX_CODES = set(_VERSTEUERT + _VERSTEUERT_IGE)


def _code_for_kz(kz_num):
    """Map a KZ number string to the account.report.line code."""
    if kz_num in _BASE_SUFFIX_CODES:
        return f'AT_{kz_num}_base'
    return f'AT_{kz_num}'


def _all_kz_numbers():
    """All KZ numbers we need from the report."""
    return (
        _LLE_TOP + _STEUERFREI + _VERSTEUERT + _VERSTEUERT_EXTRA +
        _IGE_TOP + _VERSTEUERT_IGE + _IGE_NONTAX + _VORSTEUER
    )


class L10nAtUvaReportHandler(models.AbstractModel):
    _name = 'l10n_at.uva.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'Austrian UVA Tax Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['buttons'].append({
            'name': _('XML (UVA)'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'l10n_at_export_uva_to_xml',
            'file_export_type': _('XML'),
        })

    def l10n_at_export_uva_to_xml(self, options):
        """Generate BMF-compliant U30 XML for Austrian UVA."""
        report = self.env['account.report'].browse(options['report_id'])
        company = report._get_sender_company_for_export(options)

        # Validate FASTNR
        fastnr = company._get_l10n_at_fastnr_digits()
        if not fastnr or len(fastnr) != 9:
            raise UserError(_(
                "Please configure the Finanzamt-Steuernummer (FASTNR) on company '%(company)s' "
                "before exporting UVA XML.\n\n"
                "Go to Settings \u2192 Companies \u2192 %(company)s \u2192 General Information.",
                company=company.name,
            ))

        # Get report data
        kz_values = self._extract_kz_values(report, options)

        # Build XML
        xml_content = self._build_uva_xml(fastnr, options, kz_values)

        # Validate against XSD
        self._validate_xml(xml_content)

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': xml_content,
            'file_type': 'xml',
        }

    def _extract_kz_values(self, report, options):
        """Extract KZ values from the tax report lines.

        Returns a dict mapping KZ number strings (e.g. '000', '022') to float values.
        """
        report_lines = report._get_lines(options)
        colname_to_idx = {
            col['expression_label']: idx
            for idx, col in enumerate(options.get('columns', []))
        }

        balance_idx = colname_to_idx.get('balance')
        if balance_idx is None:
            raise UserError(_("Cannot find 'balance' column in report options."))

        # Build mapping: report_line_id -> balance value
        line_id_to_value = {}
        for line in report_lines:
            col = line['columns'][balance_idx]
            if 'report_line_id' in col:
                line_id_to_value[col['report_line_id']] = col.get('no_format', 0.0)

        # Map report line codes to KZ numbers
        needed_codes = {_code_for_kz(kz): kz for kz in _all_kz_numbers()}
        report_line_records = self.env['account.report.line'].browse(line_id_to_value.keys())

        kz_values = {}
        for record in report_line_records:
            if record.code in needed_codes:
                kz_num = needed_codes[record.code]
                value = line_id_to_value.get(record.id, 0.0)
                # Most KZ fields require positive values per XSD;
                # only KZ063, KZ067, KZ090 allow negative (kzvorz type).
                # Odoo reports may return negative due to accounting sign conventions.
                if kz_num not in _ALLOW_NEGATIVE:
                    value = abs(value)
                if value:  # Only include non-zero
                    kz_values[kz_num] = value

        return kz_values

    def _build_uva_xml(self, fastnr, options, kz_values):
        """Build the ERKLAERUNGS_UEBERMITTLUNG XML structure."""
        now = datetime.now()
        paket_nr = self.env['ir.sequence'].next_by_code('l10n_at.uva.paket_nr') or '1'

        date_from = options['date']['date_from']  # 'YYYY-MM-DD'
        date_to = options['date']['date_to']      # 'YYYY-MM-DD'
        zrvon = date_from[:7]  # 'YYYY-MM'
        zrbis = date_to[:7]    # 'YYYY-MM'

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
        erkl.set('art', 'U30')
        etree.SubElement(erkl, 'SATZNR').text = '1'

        # ALLGEMEINE_DATEN
        allg = etree.SubElement(erkl, 'ALLGEMEINE_DATEN')
        etree.SubElement(allg, 'ANBRINGEN').text = 'U30'
        zrvon_el = etree.SubElement(allg, 'ZRVON')
        zrvon_el.set('type', 'jahrmonat')
        zrvon_el.text = zrvon
        zrbis_el = etree.SubElement(allg, 'ZRBIS')
        zrbis_el.set('type', 'jahrmonat')
        zrbis_el.text = zrbis
        etree.SubElement(allg, 'FASTNR').text = fastnr

        # LIEFERUNGEN_LEISTUNGEN_EIGENVERBRAUCH
        lle = etree.SubElement(erkl, 'LIEFERUNGEN_LEISTUNGEN_EIGENVERBRAUCH')

        # KZ000 is required (kznull — allows 0)
        self._add_kz(lle, '000', kz_values.get('000', 0.0), allow_zero=True)
        self._add_kz_if_present(lle, '001', kz_values)
        self._add_kz_if_present(lle, '021', kz_values)

        # STEUERFREI subsection
        steuerfrei_vals = {kz: kz_values[kz] for kz in _STEUERFREI if kz in kz_values}
        if steuerfrei_vals:
            sf = etree.SubElement(lle, 'STEUERFREI')
            for kz in _STEUERFREI:
                self._add_kz_if_present(sf, kz, kz_values)

        # VERSTEUERT subsection
        versteuert_vals = {kz: kz_values[kz] for kz in _VERSTEUERT + _VERSTEUERT_EXTRA if kz in kz_values}
        if versteuert_vals:
            vs = etree.SubElement(lle, 'VERSTEUERT')
            for kz in _VERSTEUERT + _VERSTEUERT_EXTRA:
                self._add_kz_if_present(vs, kz, kz_values)

        # INNERGEMEINSCHAFTLICHE_ERWERBE (optional section)
        ige_all = _IGE_TOP + _VERSTEUERT_IGE + _IGE_NONTAX
        ige_vals = {kz: kz_values[kz] for kz in ige_all if kz in kz_values}
        if ige_vals:
            ige = etree.SubElement(erkl, 'INNERGEMEINSCHAFTLICHE_ERWERBE')
            self._add_kz_if_present(ige, '070', kz_values, allow_zero=True)
            self._add_kz_if_present(ige, '071', kz_values)

            versteuert_ige_vals = {kz: kz_values[kz] for kz in _VERSTEUERT_IGE + _IGE_NONTAX if kz in kz_values}
            if versteuert_ige_vals:
                vige = etree.SubElement(ige, 'VERSTEUERT_IGE')
                for kz in _VERSTEUERT_IGE + _IGE_NONTAX:
                    self._add_kz_if_present(vige, kz, kz_values)

        # VORSTEUER (optional section)
        vorsteuer_vals = {kz: kz_values[kz] for kz in _VORSTEUER if kz in kz_values}
        if vorsteuer_vals:
            vst = etree.SubElement(erkl, 'VORSTEUER')
            for kz in _VORSTEUER:
                self._add_kz_if_present(vst, kz, kz_values)

        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding='iso-8859-1',
        )

    def _add_kz(self, parent, kz_num, value, allow_zero=False):
        """Add a KZ element to the parent with proper formatting."""
        if not allow_zero and not value:
            return
        el = etree.SubElement(parent, f'KZ{kz_num}')
        el.set('type', 'kz')
        # Format: up to 2 decimal places, no trailing zeros beyond cents
        el.text = f'{value:.2f}'

    def _add_kz_if_present(self, parent, kz_num, kz_values, allow_zero=False):
        """Add a KZ element only if it has a value in kz_values."""
        if kz_num in kz_values:
            self._add_kz(parent, kz_num, kz_values[kz_num], allow_zero=allow_zero)
        elif allow_zero and kz_num in _ALLOW_ZERO:
            self._add_kz(parent, kz_num, 0.0, allow_zero=True)

    def _validate_xml(self, xml_content):
        """Validate generated XML against the bundled XSD schema."""
        import os
        xsd_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data',
            'BMF_ERKLAERUNGS_UEBERMITTLUNG_U30_01_2022.xsd',
        )
        if not os.path.isfile(xsd_path):
            _logger.warning("UVA XSD schema file not found at %s, skipping validation.", xsd_path)
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
            _logger.error("UVA XSD validation failed: %s", e)
            raise UserError(_(
                "The generated XML does not conform to the BMF XSD schema:\n\n%(errors)s",
                errors=str(e),
            ))
