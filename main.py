"""FISCALITÉ360 PRO - étape 1 : socle (entreprises, Centre Fiscal, calculs)."""
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QComboBox,
    QLabel, QFormLayout, QDoubleSpinBox, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, QDate
from fiscalite360 import db, engine, seed_autres

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
        self.filtre = QComboBox(); self.filtre.addItem("Tous les pays", None)
        for r in con.execute("SELECT code, nom FROM pays ORDER BY nom"):
            self.filtre.addItem(r["nom"], r["code"])
        lay.addWidget(self.filtre)
        self.table = QTableWidget(0, len(self.COLS)); self.table.setHorizontalHeaderLabels(self.COLS)
        self.filtre.currentIndexChanged.connect(lambda _: self.refresh())
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self.save_cell)
        lay.addWidget(self.table); self.refresh()

    def refresh(self):
        self.loading = True
        pays = self.filtre.currentData()
        rows = self.con.execute("SELECT * FROM parametre WHERE (? IS NULL OR pays_code=?) "
                                "ORDER BY pays_code, impot, cle", (pays, pays)).fetchall()
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
                       ("acomptes", "Acomptes IS versés"), ("salaire", "Base mensuelle impôt sur salaires")):
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
        n = lambda x: f"{x:,}".replace(",", " ")
        txt = []
        try:
            t = engine.tva(self.con, pays, v["ventes"], v["achats"])
            txt += [f"TVA collectée : {n(t['tva_collectee'])} | déductible : {n(t['tva_deductible'])}",
                    f"TVA à payer : {n(t['tva_a_payer'])} | crédit : {n(t['credit_de_tva'])}", ""]
        except KeyError as e:
            txt += [f"TVA : {e}", ""]
        try:
            i = engine.impot_societes(self.con, pays, v["resultat"], v["ca"], v["acomptes"])
            txt += [f"IS calculé : {n(i['is_calcule'])} | IMF : {n(i['imf'])} -> retenu : {i['retenu']}",
                    f"Impôt dû : {n(i['impot_du'])} | solde à payer : {n(i['solde_a_payer'])}", ""]
        except KeyError as e:
            txt += [f"IS : {e}", ""]
        try:
            u = engine.iuts(self.con, pays, v["salaire"])
            txt += [f"Impôt sur salaires (mensuel) : {n(u['iuts'])}"]
        except KeyError as e:
            txt += [str(e)]
        nonval = self.con.execute("SELECT COUNT(*) FROM parametre WHERE pays_code=? AND statut!='VALIDE'",
                                  (pays,)).fetchone()[0]
        if nonval:
            txt += ["", f"Attention : {nonval} paramètre(s) de ce pays ne sont pas encore VALIDÉS "
                        "(Centre Fiscal). Résultats indicatifs."]
        self.out.setPlainText("\n".join(txt))

class RetenuesTab(QWidget):
    """Retenues à la source : types, calcul, registre et total à reverser."""
    def __init__(self, con):
        super().__init__(); self.con = con
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.ent = QComboBox(); self.ent.currentIndexChanged.connect(self.on_entreprise)
        self.type = QComboBox(); self.type.currentIndexChanged.connect(self.preview)
        top.addWidget(QLabel("Entreprise :")); top.addWidget(self.ent, 1)
        top.addWidget(QLabel("Type de retenue :")); top.addWidget(self.type, 2)
        lay.addLayout(top)
        row = QHBoxLayout()
        self.tiers = QLineEdit(); self.tiers.setPlaceholderText("Tiers (fournisseur, bailleur...)")
        self.brut = QDoubleSpinBox(); self.brut.setRange(0, 1e12); self.brut.setDecimals(0)
        self.brut.setGroupSeparatorShown(True); self.brut.valueChanged.connect(self.preview)
        btn = QPushButton("Enregistrer la retenue"); btn.clicked.connect(self.save)
        row.addWidget(self.tiers, 2); row.addWidget(QLabel("Montant brut :")); row.addWidget(self.brut); row.addWidget(btn)
        lay.addLayout(row)
        self.info = QLabel(""); lay.addWidget(self.info)
        lay.addWidget(QLabel("Registre des retenues opérées"))
        self.reg = QTableWidget(0, 7)
        self.reg.setHorizontalHeaderLabels(["Date", "Tiers", "Type", "Brut", "Taux", "Retenue", "Net payé"])
        self.reg.horizontalHeader().setStretchLastSection(True); lay.addWidget(self.reg)
        lay.addWidget(QLabel("Synthèse par type (à reverser au Trésor)"))
        self.syn = QTableWidget(0, 4)
        self.syn.setHorizontalHeaderLabels(["Type", "Nb", "Total retenu", "Reste à reverser"])
        self.syn.horizontalHeader().setStretchLastSection(True); lay.addWidget(self.syn)
        self.reload()

    def reload(self):
        self.ent.blockSignals(True); self.ent.clear()
        for r in self.con.execute("SELECT id, nom, pays_code FROM entreprise ORDER BY nom"):
            self.ent.addItem(f"{r['nom']} ({r['pays_code']})", (r["id"], r["pays_code"]))
        self.ent.blockSignals(False); self.on_entreprise()

    def on_entreprise(self):
        self.type.blockSignals(True); self.type.clear()
        d = self.ent.currentData()
        if d:
            for r in db.liste_retenues(self.con, d[1]):
                flag = "" if r["statut"] == "VALIDE" else "  [à valider]"
                self.type.addItem(f"{r['libelle']} - {r['valeur']*100:g} %{flag}", r["cle"])
        self.type.blockSignals(False); self.preview(); self.refresh()

    def preview(self):
        d = self.ent.currentData(); code = self.type.currentData()
        if not d or not code: self.info.setText(""); return
        r = engine.retenue_source(self.con, d[1], code, self.brut.value())
        n = lambda x: f"{x:,}".replace(",", " ")
        self.info.setText(f"Retenue : {n(r['retenue'])}   |   Net à payer au tiers : {n(r['net_a_payer'])}")

    def save(self):
        d = self.ent.currentData(); code = self.type.currentData()
        if not d or not code or not self.tiers.text().strip() or self.brut.value() <= 0:
            QMessageBox.information(self, "Retenue", "Renseignez l'entreprise, le type, le tiers et le montant."); return
        engine.enregistrer_retenue(self.con, d[0], QDate.currentDate().toString("yyyy-MM-dd"),
                                   self.tiers.text().strip(), code, self.brut.value())
        self.tiers.clear(); self.brut.setValue(0); self.refresh()

    def refresh(self):
        d = self.ent.currentData(); n = lambda x: f"{int(x or 0):,}".replace(",", " ")
        rows = self.con.execute("SELECT * FROM retenue_operee WHERE entreprise_id=? ORDER BY id DESC",
                                (d[0] if d else -1,)).fetchall()
        self.reg.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate((r["date_op"], r["tiers"], r["libelle"], n(r["montant_brut"]),
                                   f"{r['taux']*100:g} %", n(r["retenue"]), n(r["net_a_payer"]))):
                self.reg.setItem(i, j, QTableWidgetItem(str(v)))
        syn = engine.synthese_retenues(self.con, d[0]) if d else []
        self.syn.setRowCount(len(syn))
        for i, r in enumerate(syn):
            for j, v in enumerate((r["libelle"], r["nb"], n(r["retenue"]), n(r["a_reverser"]))):
                self.syn.setItem(i, j, QTableWidgetItem(str(v)))

class BaremesTab(QWidget):
    """Barème progressif de l'impôt sur les salaires, par pays (modifiable)."""
    def __init__(self, con):
        super().__init__(); self.con = con
        lay = QVBoxLayout(self)
        self.pays = QComboBox()
        for r in con.execute("SELECT code, nom FROM pays ORDER BY nom"):
            self.pays.addItem(r["nom"], r["code"])
        self.pays.currentIndexChanged.connect(lambda _: self.load())
        lay.addWidget(self.pays)
        lay.addWidget(QLabel("Tranches mensuelles : de, jusqu'à (vide = sans plafond), taux en % (ex. 12.1). "
                             "Les tranches doivent se suivre sans trou."))
        self.table = QTableWidget(0, 3); self.table.setHorizontalHeaderLabels(["De", "Jusqu'à", "Taux (%)"])
        lay.addWidget(self.table)
        row = QHBoxLayout()
        for txt, fn in (("Ajouter une tranche", self.add), ("Supprimer la tranche", self.remove),
                        ("Enregistrer le barème", self.save)):
            b = QPushButton(txt); b.clicked.connect(fn); row.addWidget(b)
        lay.addLayout(row)
        self.note = QLabel(""); lay.addWidget(self.note); self.load()

    def load(self):
        rows = self.con.execute("SELECT borne_min, borne_max, taux FROM tranche WHERE pays_code=? "
                                "AND impot='IUTS' ORDER BY ordre", (self.pays.currentData(),)).fetchall()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate((r["borne_min"], r["borne_max"], r["taux"] * 100)):
                self.table.setItem(i, j, QTableWidgetItem("" if v is None else f"{v:g}"))
        statut = self.con.execute("SELECT MIN(statut) FROM tranche WHERE pays_code=? AND impot='IUTS'",
                                  (self.pays.currentData(),)).fetchone()[0]
        self.note.setText("Aucun barème saisi pour ce pays." if not rows else
                          ("Barème à valider avec la loi de finances." if statut != "VALIDE" else "Barème validé."))

    def add(self): self.table.setRowCount(self.table.rowCount() + 1)
    def remove(self):
        r = self.table.currentRow()
        if r >= 0: self.table.removeRow(r)

    def save(self):
        tr = []
        try:
            for i in range(self.table.rowCount()):
                g = lambda j: (self.table.item(i, j).text().strip().replace(",", ".") if self.table.item(i, j) else "")
                mn, mx, tx = float(g(0)), (float(g(1)) if g(1) else None), float(g(2)) / 100
                if mx is not None and mx <= mn: raise ValueError(f"Ligne {i+1} : 'Jusqu'à' doit dépasser 'De'.")
                if i and tr[-1][1] != mn: raise ValueError(f"Ligne {i+1} : la tranche doit commencer à {tr[-1][1]}.")
                if tr and tr[-1][1] is None: raise ValueError("Une tranche sans plafond doit être la dernière.")
                tr.append((mn, mx, tx))
        except (ValueError, TypeError) as e:
            QMessageBox.warning(self, "Barème invalide", str(e)); return
        p = self.pays.currentData()
        self.con.execute("DELETE FROM tranche WHERE pays_code=? AND impot='IUTS'", (p,))
        for k, (mn, mx, tx) in enumerate(tr, 1):
            self.con.execute("INSERT INTO tranche (pays_code, impot, ordre, borne_min, borne_max, taux, statut) "
                             "VALUES (?, 'IUTS', ?, ?, ?, ?, 'A_VALIDER')", (p, k, mn, mx, tx))
        self.con.commit(); self.load()

class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("FISCALITÉ360 PRO"); self.resize(900, 600)
        self.con = db.connect(); seed_autres.seed_tous(self.con)
        tabs = QTabWidget(); self.calcul = CalculTab(self.con)
        self.retenues = RetenuesTab(self.con)
        tabs.addTab(EntreprisesTab(self.con, lambda: (self.calcul.reload(), self.retenues.reload())), "Entreprises")
        tabs.addTab(CentreFiscalTab(self.con), "Centre Fiscal")
        tabs.addTab(BaremesTab(self.con), "Barèmes salaires")
        tabs.addTab(self.calcul, "Calculs")
        tabs.addTab(self.retenues, "Retenues à la source")
        self.setCentralWidget(tabs)

if __name__ == "__main__":
    app = QApplication(sys.argv); w = Main(); w.show(); sys.exit(app.exec_())
