import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fiscalite360 import db, engine, seed_bf, seed_autres

def con():
    c = db.connect(":memory:"); seed_autres.seed_tous(c); return c

def test_tva():
    r = engine.tva(con(), "BF", 10_000_000, 4_000_000)
    assert r["tva_collectee"] == 1_800_000 and r["tva_a_payer"] == 1_080_000

def test_tva_credit():
    r = engine.tva(con(), "BF", 1_000_000, 5_000_000)
    assert r["tva_a_payer"] == 0 and r["credit_de_tva"] == 720_000

def test_is_retient_imf_si_deficit():
    r = engine.impot_societes(con(), "BF", -500_000, 100_000_000)
    assert r["retenu"] == "IMF" and r["impot_du"] == 1_000_000

def test_is_normal():
    r = engine.impot_societes(con(), "BF", 40_000_000, 100_000_000, acomptes_verses=2_000_000)
    assert r["is_calcule"] == 11_000_000 and r["solde_a_payer"] == 9_000_000

def test_progressif():
    # 100 000 : 20 000*12,1% + 30 000*13,9% + 20 000*15,7% = 2420+4170+3140
    assert engine.iuts(con(), "BF", 100_000)["iuts"] == 9_730

def test_param_modifiable():
    c = con()
    c.execute("UPDATE parametre SET valeur=0.19 WHERE impot='TVA'")
    assert engine.tva(c, "BF", 1_000_000, 0)["tva_collectee"] == 190_000

def test_param_manquant():
    import pytest
    with pytest.raises(KeyError):
        engine.tva(con(), "XX", 1, 1)


def test_retenue_source():
    c = con()
    r = engine.retenue_source(c, "BF", "PRESTATIONS_RESIDENT", 2_000_000)
    assert r["retenue"] == 100_000 and r["net_a_payer"] == 1_900_000

def test_registre_retenues():
    c = con()
    c.execute("INSERT INTO entreprise (nom, pays_code) VALUES ('Test','BF')")
    engine.enregistrer_retenue(c, 1, "2026-10-02", "Fournisseur A", "LOYERS", 1_000_000)
    engine.enregistrer_retenue(c, 1, "2026-10-03", "Fournisseur B", "LOYERS", 500_000)
    s = engine.synthese_retenues(c, 1)
    assert len(s) == 1 and s[0]["retenue"] == 150_000 and s[0]["a_reverser"] == 150_000


def test_six_pays():
    c = con()
    codes = sorted(r["code"] for r in c.execute("SELECT code FROM pays"))
    assert codes == ["BF", "BJ", "CI", "ML", "NE", "SN"]

def test_chaque_pays_calcule_et_a_ses_retenues():
    c = con()
    for code in ["BF", "BJ", "CI", "ML", "NE", "SN"]:
        assert engine.tva(c, code, 1_000_000, 0)["tva_collectee"] > 0
        assert engine.impot_societes(c, code, 10_000_000, 100_000_000)["impot_du"] > 0
        assert len(db.liste_retenues(c, code)) == 6

def test_tva_niger_differente():
    assert engine.tva(con(), "NE", 1_000_000, 0)["tva_collectee"] == 190_000

def test_plafond_imf_senegal():
    r = engine.impot_societes(con(), "SN", -1, 10_000_000_000)   # 0,5 % = 50 M, plafonné
    assert r["imf"] == 5_000_000

def test_bareme_salaires_absent_hors_bf():
    import pytest
    with pytest.raises(KeyError):
        engine.iuts(con(), "SN", 100_000)
