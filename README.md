# Austria - UVA/ZM XML Export (Datentraeger)

Odoo 18 module for exporting Austrian tax reports as BMF-compliant XML files for [FinanzOnline Datenstromübermittlung](https://finanzonline.bmf.gv.at/).

## What it does

Adds XML export buttons to two Austrian tax reports in Odoo:

- **UVA (U30)** - Umsatzsteuervoranmeldung (VAT return)
- **ZM (U13)** - Zusammenfassende Meldung (EC Sales List)

The generated XML files conform to the official BMF XSD schemas and can be uploaded directly to FinanzOnline via Eingaben > Upload > Datenstromübermittlung.

## Features

- XML export button on the Austrian Tax Report (UVA/U30)
- XML export button on the Austrian EC Sales Report (ZM/U13)
- XSD validation before download - invalid XML is blocked with a clear error message
- Maps all KZ fields from the Odoo tax report to the correct XML structure
- FASTNR (Finanzamt-Steuernummer) field on company settings with format validation
- Supports monthly and quarterly reporting periods
- Auto-incrementing PAKET_NR via `ir.sequence`

## KZ Fields (UVA)

All standard UVA Kennzahlen are mapped:

| Section | KZ |
|---|---|
| Lieferungen/Leistungen | 000, 001, 021 |
| Steuerfrei mit Vorsteuerabzug | 011, 012, 015, 017, 018 |
| Steuerfrei ohne Vorsteuerabzug | 019, 016, 020 |
| Versteuert (Bemessungsgrundlage) | 022, 029, 006, 037, 052, 007 |
| Steuerschuld | 056, 057, 048, 044, 032 |
| Innergemeinschaftliche Erwerbe | 070, 071, 072, 073, 008, 088, 076, 077 |
| Vorsteuer | 060, 061, 083, 065, 066, 082, 087, 089, 064, 062, 063, 067 |
| Sonstige Berichtigungen | 090 |

Zero-value fields are omitted. Negative values are converted to absolute values except for KZ063, KZ067, and KZ090 which allow negative values per the XSD.

## Requirements

- Odoo 18 Enterprise
- `l10n_at` (Austrian localization - included in Odoo)
- `l10n_at_reports` (Austrian reporting - Odoo Enterprise)

## Setup

1. Install the module from Apps
2. Go to Settings > Companies > your company > General Information
3. Set the **Finanzamt-Steuernummer (FASTNR)** field (format: `XX-NNN/NNNN`, e.g. `09-999/9999`)
4. Open the Tax Report or EC Sales Report and use the XML export button

## FASTNR

The Finanzamt-Steuernummer is your Austrian tax office number. It is validated against the list of known Austrian Finanzamt prefixes (FA codes). The formatted value (e.g. `09-999/9999`) is stored on the company and stripped to 9 digits (e.g. `099999999`) for the XML.

## Testing

Before submitting to FinanzOnline for real, use the **Testübermittlung** option:

1. Export the XML from Odoo
2. Log in to FinanzOnline
3. Go to Eingaben > Upload > Datenstromübermittlung
4. Check the "Testfall" checkbox
5. Upload the XML

A successful test returns: *"XML-File wurde gesendet, es wurde 1 Erklärung übermittelt. Das File wurde nur für Testzwecke übermittelt!"*

## Disclaimer

**This software is provided as-is, without any warranty or guarantee of correctness.** Use it at your own risk. The authors accept no liability for any damages, tax penalties, or financial losses arising from the use of this module. Always verify generated XML files against the official BMF specifications and use FinanzOnline's Testübermittlung before submitting real declarations. You are solely responsible for the accuracy of your tax filings.

## License

LGPL-3

## BMF References

### UVA (U30) - Umsatzsteuervoranmeldung ab 01/2022

| Document | Link |
|---|---|
| Overview (Allgemeines) | [PDF](https://www.bmf.gv.at/dam/jcr:8b27d8e4-413d-4a3c-8ff0-2c946ce7bf09/BMF_Allgemeines_UVA_01_2022.pdf) |
| XML structure (example) | [XML](https://www.bmf.gv.at/dam/jcr:d0ac5c10-64e5-44ca-abc9-2a0cb3b14c56/BMF_ERKLAERUNGS_UEBERMITTLUNG_U30_01_2022.xml) |
| XSD schema | [XSD](https://www.bmf.gv.at/dam/jcr:5deafd50-12d6-4ac3-a9f7-0e234c690db2/BMF_ERKLAERUNGS_UEBERMITTLUNG_U30_01_2022.xsd) |
| Validation rules (Prüfungen) | [PDF](https://www.bmf.gv.at/dam/jcr:61659322-96da-4788-863f-35ebf0213024/BMF_Pruefungen_UVA_ab_01_2022.pdf) |

### ZM (U13) - Zusammenfassende Meldung

| Document | Link |
|---|---|
| XSD schema | [XSD](https://www.bmf.gv.at/dam/jcr:7ff03520-deca-4ef8-aa60-b8ff206bb581/BMF_XSD_Schema_Zusammenfassende_Meldung.xsd) |

### General

- [BMF Softwarehersteller - Erklärungen und Anträge](https://www.bmf.gv.at/services/finanzonline/informationen-fuer-softwarehersteller/softwarehersteller-erklarungen-und-antraege.html)
- [BMF Datenstromübermittlung](https://www.bmf.gv.at/services/finanzonline/informationen-fuer-softwarehersteller/datenstromuebermittlung.html)
