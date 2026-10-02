"""Valeurs de DÉPART pour le Burkina Faso.
ATTENTION : toutes marquées A_VALIDER. Elles doivent être vérifiées avec le Code
général des impôts et la loi de finances en vigueur avant tout usage réel,
puis modifiées dans le Centre Fiscal si besoin."""

PAYS = ("BF", "Burkina Faso", "XOF")

# (impot, cle, valeur, libelle)
PARAMETRES = [
    ("TVA", "taux_normal", 0.18, "Taux normal de TVA"),
    ("IS",  "taux", 0.275, "Taux de l'impôt sur les sociétés"),
    ("IS",  "imf_taux", 0.005, "Impôt minimum forfaitaire : taux sur chiffre d'affaires"),
    ("IS",  "imf_minimum", 1000000, "Impôt minimum forfaitaire : plancher (FCFA)"),
]

# Barème mensuel IUTS (impot sur traitements et salaires) : (min, max, taux)
# Exemple de structure ; valeurs à confirmer.
TRANCHES_IUTS = [
    (0, 30000, 0.0),
    (30000, 50000, 0.121),
    (50000, 80000, 0.139),
    (80000, 120000, 0.157),
    (120000, 170000, 0.184),
    (170000, 250000, 0.217),
    (250000, None, 0.25),
]

def seed(con):
    con.execute("INSERT OR IGNORE INTO pays VALUES (?,?,?)", PAYS)
    for impot, cle, val, lib in PARAMETRES:
        con.execute("INSERT OR IGNORE INTO parametre (pays_code, impot, cle, valeur, libelle) "
                    "VALUES ('BF',?,?,?,?)", (impot, cle, val, lib))
    for i, (mn, mx, t) in enumerate(TRANCHES_IUTS, 1):
        con.execute("INSERT OR IGNORE INTO tranche (pays_code, impot, ordre, borne_min, borne_max, taux) "
                    "VALUES ('BF','IUTS',?,?,?,?)", (i, mn, mx, t))
    con.commit()
