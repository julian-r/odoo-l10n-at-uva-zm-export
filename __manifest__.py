{
    "name": "Austria - UVA/ZM XML Export (Datentraeger)",
    "version": "18.0.1.0",
    "category": "Accounting/Localizations/Reporting",
    "summary": "Export Austrian UVA (U30) and ZM (U13) reports as BMF-compliant XML for FinanzOnline",
    "author": "Julian R",
    "website": "https://github.com/julian-r/odoo-l10n-at-uva-zm-export",
    "license": "LGPL-3",
    "depends": [
        "l10n_at",
        "l10n_at_reports",
    ],
    "data": [
        "data/ir_sequence.xml",
        "data/account_report_data.xml",
        "views/res_company_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
