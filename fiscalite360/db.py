"""Base SQLite : schéma + données initiales (tout est paramétrable, rien en dur)."""
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".fiscalite360" / "fiscalite360.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS pays (
    code TEXT PRIMARY KEY, nom TEXT NOT NULL, devise TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entreprise (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL, pays_code TEXT NOT NULL REFERENCES pays(code),
    nif TEXT, regime TEXT NOT NULL DEFAULT 'reel_normal',
    logo_path TEXT);
CREATE TABLE IF NOT EXISTS parametre (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pays_code TEXT NOT NULL REFERENCES pays(code),
    impot TEXT NOT NULL, cle TEXT NOT NULL,
    valeur REAL NOT NULL, libelle TEXT,
    statut TEXT NOT NULL DEFAULT 'A_VALIDER',   -- A_VALIDER | VALIDE
    reference_legale TEXT,                       -- à renseigner par l'utilisateur
    date_maj TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (pays_code, impot, cle));
CREATE TABLE IF NOT EXISTS retenue_operee (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id INTEGER NOT NULL REFERENCES entreprise(id),
    date_op TEXT NOT NULL, tiers TEXT NOT NULL,
    code TEXT NOT NULL, libelle TEXT,
    montant_brut INTEGER NOT NULL, taux REAL NOT NULL,
    retenue INTEGER NOT NULL, net_a_payer INTEGER NOT NULL,
    reversee INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS tranche (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pays_code TEXT NOT NULL REFERENCES pays(code),
    impot TEXT NOT NULL, ordre INTEGER NOT NULL,
    borne_min REAL NOT NULL, borne_max REAL,     -- NULL = sans plafond
    taux REAL NOT NULL,
    statut TEXT NOT NULL DEFAULT 'A_VALIDER',
    UNIQUE (pays_code, impot, ordre));
"""

def connect(path=None):
    p = Path(path) if path else DB_PATH
    if str(p) != ":memory:":
        p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con

def get_param(con, pays, impot, cle):
    r = con.execute("SELECT valeur FROM parametre WHERE pays_code=? AND impot=? AND cle=?",
                    (pays, impot, cle)).fetchone()
    if r is None:
        raise KeyError(f"Paramètre manquant : {pays}/{impot}/{cle} (voir Centre Fiscal)")
    return r["valeur"]

def get_param_opt(con, pays, impot, cle, defaut=0):
    r = con.execute("SELECT valeur FROM parametre WHERE pays_code=? AND impot=? AND cle=?",
                    (pays, impot, cle)).fetchone()
    return defaut if r is None else r["valeur"]

def get_tranches(con, pays, impot):
    rows = con.execute("SELECT borne_min, borne_max, taux FROM tranche "
                       "WHERE pays_code=? AND impot=? ORDER BY ordre", (pays, impot)).fetchall()
    if not rows:
        raise KeyError(f"Barème de l'impôt sur les salaires manquant pour {pays} : saisissez-le dans l'onglet Barèmes")
    return [(r["borne_min"], r["borne_max"], r["taux"]) for r in rows]

def liste_retenues(con, pays):
    """Types de retenues à la source du pays (stockés dans parametre, impot='RAS')."""
    return con.execute("SELECT cle, libelle, valeur, statut FROM parametre "
                       "WHERE pays_code=? AND impot='RAS' ORDER BY cle", (pays,)).fetchall()
