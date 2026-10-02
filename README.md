# FISCALITÉ360 PRO - Étape 1 (socle, Burkina Faso)

Lancer : `pip install PyQt5` puis `python main.py`
Tests : `pytest tests`

- Les règles fiscales sont dans la base (tables `parametre` et `tranche`), jamais dans le code.
- `fiscalite360/seed_bf.py` contient des valeurs de départ, toutes en statut A_VALIDER.
  Vérifiez-les avec le CGI et la loi de finances en vigueur, puis passez-les à VALIDE dans le Centre Fiscal.
- Ajouter un pays = ajouter un fichier seed (pays + paramètres + barèmes), sans toucher au moteur.
