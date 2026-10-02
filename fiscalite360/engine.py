"""Moteur de calcul. Aucune règle en dur : tout vient des tables de paramètres."""
from decimal import Decimal, ROUND_HALF_UP
from .db import get_param, get_param_opt, get_tranches, liste_retenues

def _d(x): return Decimal(str(x))
def fcfa(x):  # arrondi au franc
    return int(_d(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def tva(con, pays, ventes_ht, achats_ht_deductibles, credit_precedent=0):
    taux = _d(get_param(con, pays, "TVA", "taux_normal"))
    collectee = _d(ventes_ht) * taux
    deductible = _d(achats_ht_deductibles) * taux
    net = collectee - deductible - _d(credit_precedent)
    return {"tva_collectee": fcfa(collectee), "tva_deductible": fcfa(deductible),
            "tva_a_payer": max(fcfa(net), 0), "credit_de_tva": max(-fcfa(net), 0)}

def impot_societes(con, pays, resultat_fiscal, chiffre_affaires, acomptes_verses=0):
    taux = _d(get_param(con, pays, "IS", "taux"))
    imf_taux = _d(get_param(con, pays, "IS", "imf_taux"))
    imf_min = _d(get_param(con, pays, "IS", "imf_minimum"))
    is_calc = max(_d(resultat_fiscal), Decimal(0)) * taux
    imf = max(_d(chiffre_affaires) * imf_taux, imf_min)
    imf_max = _d(get_param_opt(con, pays, "IS", "imf_maximum", 0))
    if imf_max > 0:
        imf = min(imf, imf_max)
    du = max(is_calc, imf)
    solde = du - _d(acomptes_verses)
    return {"is_calcule": fcfa(is_calc), "imf": fcfa(imf), "impot_du": fcfa(du),
            "retenu": "IMF" if imf > is_calc else "IS",
            "solde_a_payer": max(fcfa(solde), 0), "excedent": max(-fcfa(solde), 0)}

def progressif(base, tranches):
    """Barème par tranches progressives. tranches = [(min, max|None, taux)]."""
    base = _d(base); total = Decimal(0); detail = []
    for mn, mx, taux in tranches:
        if base <= _d(mn):
            break
        haut = base if mx is None else min(base, _d(mx))
        part = (haut - _d(mn)) * _d(taux)
        total += part
        detail.append({"de": mn, "a": mx, "taux": taux, "impot": fcfa(part)})
    return fcfa(total), detail

def iuts(con, pays, base_imposable_mensuelle):
    total, detail = progressif(base_imposable_mensuelle, get_tranches(con, pays, "IUTS"))
    return {"iuts": total, "detail": detail}


def retenue_source(con, pays, code, montant_brut):
    """Retenue à la source = brut x taux ; net à payer au tiers = brut - retenue."""
    taux = _d(get_param(con, pays, "RAS", code))
    ret = fcfa(_d(montant_brut) * taux)
    return {"code": code, "taux": float(taux), "montant_brut": fcfa(montant_brut),
            "retenue": ret, "net_a_payer": fcfa(montant_brut) - ret}

def enregistrer_retenue(con, entreprise_id, date_op, tiers, code, montant_brut):
    pays = con.execute("SELECT pays_code FROM entreprise WHERE id=?", (entreprise_id,)).fetchone()["pays_code"]
    r = retenue_source(con, pays, code, montant_brut)
    lib = next((x["libelle"] for x in liste_retenues(con, pays) if x["cle"] == code), code)
    con.execute("INSERT INTO retenue_operee (entreprise_id,date_op,tiers,code,libelle,montant_brut,taux,retenue,net_a_payer) "
                "VALUES (?,?,?,?,?,?,?,?,?)", (entreprise_id, date_op, tiers, code, lib,
                r["montant_brut"], r["taux"], r["retenue"], r["net_a_payer"]))
    con.commit()
    return r

def synthese_retenues(con, entreprise_id):
    """Totaux par type de retenue, et montant restant à reverser au Trésor."""
    return con.execute("SELECT libelle, COUNT(*) AS nb, SUM(montant_brut) AS brut, SUM(retenue) AS retenue, "
                       "SUM(CASE WHEN reversee=0 THEN retenue ELSE 0 END) AS a_reverser "
                       "FROM retenue_operee WHERE entreprise_id=? GROUP BY code ORDER BY libelle",
                       (entreprise_id,)).fetchall()
