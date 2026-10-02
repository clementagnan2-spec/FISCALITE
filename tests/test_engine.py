import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fiscalite360 import db, engine, seed_bf

def con():
    c = db.connect(":memory:"); seed_bf.seed(c); return c

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
        engine.tva(con(), "SN", 1, 1)
