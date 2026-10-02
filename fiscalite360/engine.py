"""Moteur de calcul. Aucune règle en dur : tout vient des tables de paramètres."""
from decimal import Decimal, ROUND_HALF_UP
from .db import get_param, get_tranches

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
