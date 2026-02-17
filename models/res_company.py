import re

from odoo import fields, models, api
from odoo.exceptions import ValidationError

# Valid Finanzamt prefixes from BMF Finanzamtsliste
_VALID_FA_PREFIXES = {
    '03', '06', '07', '08', '09', '10', '12',
    '15', '16', '22', '23', '29',
    '38',
    '41', '46', '51', '52', '53', '54',
    '57', '61',
    '67', '68', '69', '71', '72',
    '81', '83', '84',
    '90', '91', '93',
    '98',
}


def _normalize_fastnr(value):
    """Normalize a FASTNR input like '68/123 1234' or '681231234' to 9 bare digits."""
    if not value:
        return value
    return re.sub(r'[^0-9]', '', value.strip())


def _format_fastnr(digits):
    """Format 9 bare digits as 'XX-NNN/NNNN'."""
    if not digits or len(digits) != 9:
        return digits
    return f'{digits[:2]}-{digits[2:5]}/{digits[5:]}'


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_at_fastnr = fields.Char(
        string="Finanzamt-Steuernummer (FASTNR)",
        size=12,  # room for formatted display 'XX/NNN NNNN'
        help="Austrian tax office number (Finanzamt-Steuernummer) for FinanzOnline submissions.\n"
             "Format: XX-NNN/NNNN (e.g. 68-791/8789) where the first two digits are the Finanzamt code.\n"
             "Not the UID/VAT number (ATU...).",
    )

    @api.onchange('l10n_at_fastnr')
    def _onchange_l10n_at_fastnr(self):
        if self.l10n_at_fastnr:
            digits = _normalize_fastnr(self.l10n_at_fastnr)
            if len(digits) == 9:
                self.l10n_at_fastnr = _format_fastnr(digits)
    def write(self, vals):
        if 'l10n_at_fastnr' in vals and vals['l10n_at_fastnr']:
            digits = _normalize_fastnr(vals['l10n_at_fastnr'])
            if len(digits) == 9:
                vals['l10n_at_fastnr'] = _format_fastnr(digits)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('l10n_at_fastnr'):
                digits = _normalize_fastnr(vals['l10n_at_fastnr'])
                if len(digits) == 9:
                    vals['l10n_at_fastnr'] = _format_fastnr(digits)
        return super().create(vals_list)

    @api.constrains('l10n_at_fastnr')
    def _check_l10n_at_fastnr(self):
        for company in self:
            if company.l10n_at_fastnr:
                digits = _normalize_fastnr(company.l10n_at_fastnr)
                if not digits.isdigit() or len(digits) != 9:
                    raise ValidationError(
                        "FASTNR must be 9 digits. Use format: XX-NNN/NNNN (e.g. 68-791/8789)."
                    )
                prefix = digits[:2]
                if prefix not in _VALID_FA_PREFIXES:
                    raise ValidationError(
                        f"Unknown Finanzamt prefix '{prefix}'. "
                        f"Valid prefixes: {', '.join(sorted(_VALID_FA_PREFIXES))}."
                    )
                nr = int(digits)
                if nr < 10000010 or nr > 989999999:
                    raise ValidationError("FASTNR must be between 010000010 and 989999999.")

    def _get_l10n_at_fastnr_digits(self):
        """Return the FASTNR as 9 bare digits for XML generation."""
        self.ensure_one()
        return _normalize_fastnr(self.l10n_at_fastnr) if self.l10n_at_fastnr else ''
