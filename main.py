"""FISCALITÉ360 PRO - étape 1 : socle (entreprises, Centre Fiscal, calculs)."""
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QComboBox,
    QLabel, QFormLayout, QDoubleSpinBox, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt
from fiscalite360 import db, engine, seed_bf

class EntreprisesTab(QWidget):
    def __init__(self, con, on_change):
        super().__init__(); self.con = con; self.on_change = on_change
        lay = QVBoxLayout(self)
        form = QHBoxLayout()
        self.nom = QLineEdit(); self.nom.setPlaceholderText("Nom de l'entreprise")
        self.nif = QLineEdit(); self.nif.setPlaceholderText("NIF / IFU")
        self.pays = QComboBox()
        for r in con.execute("SELECT code, nom FROM pays ORDER BY nom"):
            self.pays.addItem(r["nom"], r["code"])
        btn = QPushButton("Ajouter"); btn.clicked.connect(self.add)
        for w in (self.nom, self.nif, self.pays, btn): form.addWidget(w)
        lay.addLayout(form)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Entreprise", "Pays", "NIF"])
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table); self.refresh()

    def add(self):
        if not self.nom.text().strip():
            return
        self.con.execute("INSERT INTO entreprise (nom, pays_code, nif) VALUES (?,?,?)",
                         (self.nom.text().strip(), self.pays.currentData(), self.nif.text().strip()))
        self.con.commit(); self.nom.clear(); self.nif.clear(); self.refresh(); self.on_change()

    def refresh(self):
        rows = self.con.execute("SELECT e.nom, p.nom AS pays, e.nif FROM entreprise e "
                                "JOIN pays p ON p.code=e.pays_code ORDER BY e.nom").fetchall()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, k in enumerate(("nom", "pays", "nif")):
                self.table.setItem(i, j, QTableWidgetItem(r[k] or ""))

class CentreFiscalTab(QWidget):
    COLS = ["Pays", "Impôt", "Clé", "Libellé", "Valeur", "Statut", "Réf. légale"]
    def __init__(self, con):
        super().__init__(); self.con = con; self.loading = False
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Modifiez ici taux, seuils et références. Passez le statut à VALIDE "
                             "une fois la valeur vérifiée dans la loi de finances."))
        self.table = QTableWidget(0, len(self.COLS)); self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self.save_cell)
        lay.addWidget(self.table); self.refresh()

    def refresh(self):
        self.loading = True
        rows = self.con.execute("SELECT * FROM parametre ORDER BY pays_code, impot, cle").fetchall()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r["pays_code"], r["impot"], r["cle"], r["libelle"] or "", r["valeur"],
                    r["statut"], r["reference_legale"] or ""]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v)); it.setData(Qt.UserRole, r["id"])
                if j < 4:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, j, it)
        self.loading = False

    def save_cell(self, it):
        if self.loading or it.column() < 4: return
        col = {4: "valeur", 5: "statut", 6: "reference_legale"}[it.column()]
        val = it.text()
        try:
            if col == "valeur": val = float(val.replace(",", "."))
            if col == "statut" and val not in ("A_VALIDER", "VALIDE"):
                raise ValueError("Statut : A_VALIDER ou VALIDE")
        except ValueError as e:
            QMessageBox.warning(self, "Valeur invalide", str(e)); self.refresh(); return
        self.con.execute(f"UPDATE parametre SET {col}=?, date_maj=CURRENT_TIMESTAMP WHERE id=?",
                         (val, it.data(Qt.UserRole)))
        self.con.commit()

class CalculTab(QWidget):
    def __init__(self, con):
        super().__init__(); self.con = con
        lay = QVBoxLayout(self)
        self.ent = QComboBox(); lay.addWidget(self.ent)
        form = QFormLayout()
        self.f = {}
        for k, lab in (("ventes", "Ventes HT (période)"), ("achats", "Achats HT déductibles"),
                       ("resultat", "Résultat fiscal (IS)"), ("ca", "Chiffre d'affaires annuel (IS)"),
                       ("acomptes", "Acomptes IS versés"), ("salaire", "Base IUTS mensuelle")):
            s = QDoubleSpinBox(); s.setRange(-1e12, 1e12); s.setDecimals(0); s.setGroupSeparatorShown(True)
            self.f[k] = s; form.addRow(lab, s)
        lay.addLayout(form)
        b = QPushButton("Calculer"); b.clicked.connect(self.calc); lay.addWidget(b)
        self.out = QTextEdit(); self.out.setReadOnly(True); lay.addWidget(self.out)
        self.reload()

    def reload(self):
        self.ent.clear()
        for r in self.con.execute("SELECT id, nom, pays_code FROM entreprise ORDER BY nom"):
            self.ent.addItem(f"{r['nom']} ({r['pays_code']})", r["pays_code"])

    def calc(self):
        pays = self.ent.currentData()
        if not pays:
            self.out.setPlainText("Ajoutez d'abord une entreprise."); return
        v = {k: s.value() for k, s in self.f.items()}
        try:
            t = engine.tva(self.con, pays, v["ventes"], v["achats"])
            i = engine.impot_societes(self.con, pays, v["resultat"], v["ca"], v["acomptes"])
            u = engine.iuts(self.con, pays, v["salaire"])
        except KeyError as e:
            self.out.setPlainText(str(e)); return
        n = lambda x: f"{x:,}".replace(",", " ")
        nonval = self.con.execute("SELECT COUNT(*) FROM parametre WHERE pays_code=? AND statut!='VALIDE'",
                                  (pays,)).fetchone()[0]
        txt = [f"TVA collectée : {n(t['tva_collectee'])} | déductible : {n(t['tva_deductible'])}",
               f"TVA à payer : {n(t['tva_a_payer'])} | crédit : {n(t['credit_de_tva'])}", "",
               f"IS calculé : {n(i['is_calcule'])} | IMF : {n(i['imf'])} -> retenu : {i['retenu']}",
               f"Impôt dû : {n(i['impot_du'])} | solde à payer : {n(i['solde_a_payer'])}", "",
               f"IUTS mensuel : {n(u['iuts'])}"]
        if nonval:
            txt += ["", f"Attention : {nonval} paramètre(s) de ce pays ne sont pas encore VALIDÉS "
                        "(Centre Fiscal). Résultats indicatifs."]
        self.out.setPlainText("\n".join(txt))

class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("FISCALITÉ360 PRO"); self.resize(900, 600)
        self.con = db.connect(); seed_bf.seed(self.con)
        tabs = QTabWidget(); self.calcul = CalculTab(self.con)
        tabs.addTab(EntreprisesTab(self.con, self.calcul.reload), "Entreprises")
        tabs.addTab(CentreFiscalTab(self.con), "Centre Fiscal")
        tabs.addTab(self.calcul, "Calculs")
        self.setCentralWidget(tabs)

if __name__ == "__main__":
    app = QApplication(sys.argv); w = Main(); w.show(); sys.exit(app.exec_())
