"""Valeurs de DÉPART pour Sénégal, Côte d'Ivoire, Mali, Bénin, Niger.
TOUT est marqué A_VALIDER. Ce sont des ordres de grandeur issus de ma mémoire :
chaque valeur doit être vérifiée avec le Code général des impôts et la loi de
finances en vigueur du pays, puis corrigée dans le Centre Fiscal.
Les barèmes de l'impôt sur les salaires ne sont PAS préremplis (onglet Barèmes)."""
from . import seed_bf

RAS_LIBELLES = {
    "PRESTATIONS_RESIDENT": "Retenue sur prestations de services (fournisseur résident)",
    "PRESTATIONS_NON_RESIDENT": "Retenue sur prestations payées à un non-résident",
    "LOYERS": "Retenue sur loyers versés",
    "HONORAIRES_COMMISSIONS": "Retenue sur honoraires, commissions, courtages",
    "DIVIDENDES_IRCM": "Retenue sur dividendes (revenus de capitaux mobiliers)",
    "FOURNISSEUR_SANS_IFU": "Retenue majorée : fournisseur sans identifiant fiscal",
}

PAYS_DATA = {
    "SN": {"nom": "Sénégal", "tva": 0.18, "is": 0.30, "imf_taux": 0.005, "imf_min": 500000, "imf_max": 5000000,
           "ras": {"PRESTATIONS_RESIDENT": 0.05, "PRESTATIONS_NON_RESIDENT": 0.20, "LOYERS": 0.15,
                   "HONORAIRES_COMMISSIONS": 0.05, "DIVIDENDES_IRCM": 0.10, "FOURNISSEUR_SANS_IFU": 0.25}},
    "CI": {"nom": "Côte d'Ivoire", "tva": 0.18, "is": 0.25, "imf_taux": 0.005, "imf_min": 3000000, "imf_max": 0,
           "ras": {"PRESTATIONS_RESIDENT": 0.075, "PRESTATIONS_NON_RESIDENT": 0.20, "LOYERS": 0.15,
                   "HONORAIRES_COMMISSIONS": 0.075, "DIVIDENDES_IRCM": 0.15, "FOURNISSEUR_SANS_IFU": 0.25}},
    "ML": {"nom": "Mali", "tva": 0.18, "is": 0.30, "imf_taux": 0.01, "imf_min": 500000, "imf_max": 0,
           "ras": {"PRESTATIONS_RESIDENT": 0.05, "PRESTATIONS_NON_RESIDENT": 0.15, "LOYERS": 0.15,
                   "HONORAIRES_COMMISSIONS": 0.05, "DIVIDENDES_IRCM": 0.10, "FOURNISSEUR_SANS_IFU": 0.25}},
    "BJ": {"nom": "Bénin", "tva": 0.18, "is": 0.30, "imf_taux": 0.01, "imf_min": 500000, "imf_max": 0,
           "ras": {"PRESTATIONS_RESIDENT": 0.05, "PRESTATIONS_NON_RESIDENT": 0.20, "LOYERS": 0.12,
                   "HONORAIRES_COMMISSIONS": 0.05, "DIVIDENDES_IRCM": 0.10, "FOURNISSEUR_SANS_IFU": 0.25}},
    "NE": {"nom": "Niger", "tva": 0.19, "is": 0.30, "imf_taux": 0.01, "imf_min": 500000, "imf_max": 0,
           "ras": {"PRESTATIONS_RESIDENT": 0.05, "PRESTATIONS_NON_RESIDENT": 0.16, "LOYERS": 0.15,
                   "HONORAIRES_COMMISSIONS": 0.05, "DIVIDENDES_IRCM": 0.10, "FOURNISSEUR_SANS_IFU": 0.25}},
}

def seed_pays(con, code):
    d = PAYS_DATA[code]
    con.execute("INSERT OR IGNORE INTO pays VALUES (?,?,'XOF')", (code, d["nom"]))
    lignes = [("TVA", "taux_normal", d["tva"], "Taux normal de TVA"),
              ("IS", "taux", d["is"], "Taux de l'impôt sur les sociétés"),
              ("IS", "imf_taux", d["imf_taux"], "Impôt minimum forfaitaire : taux sur chiffre d'affaires"),
              ("IS", "imf_minimum", d["imf_min"], "Impôt minimum forfaitaire : plancher (FCFA)"),
              ("IS", "imf_maximum", d["imf_max"], "Impôt minimum forfaitaire : plafond (FCFA, 0 = aucun)")]
    lignes += [("RAS", c, t, RAS_LIBELLES[c]) for c, t in d["ras"].items()]
    for impot, cle, val, lib in lignes:
        con.execute("INSERT OR IGNORE INTO parametre (pays_code, impot, cle, valeur, libelle) VALUES (?,?,?,?,?)",
                    (code, impot, cle, val, lib))
    con.commit()

def seed_tous(con):
    seed_bf.seed(con)
    for code in PAYS_DATA:
        seed_pays(con, code)
