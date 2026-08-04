# KPI de vente — Tunisie Télécom

Application de **calcul, suivi et prévision** des indicateurs de performance
(KPI) de vente, réalisée dans le cadre d'un **Projet de Fin d'Études** (Licence
Appliquée) chez Tunisie Télécom.

> 🔗 **Application en ligne :** https://tt-kpi-dashboard-bk6wgnynlifm4opdpbcbrb.streamlit.app/

À partir des ventes journalières par sous-catégorie et des objectifs mensuels
par catégorie, l'application :

1. permet la **saisie / import mensuel** des réalisations (fichier Excel ou CSV)
   avec **recalcul automatique** des KPI ;
2. calcule le **cumul mensuel** des ventes et le **taux de réalisation** vs objectif ;
3. suit le **cumul annuel** (réalisé cumulé vs objectif cumulé) ;
4. visualise le tout dans un **dashboard interactif** (Streamlit) ;
5. **prévoit** les ventes futures (Machine Learning — modèle Prophet) ;
6. estime la **probabilité d'atteindre l'objectif annuel** ;
7. **détecte les jours de vente anormaux** (z-score) ;
8. analyse les réalisations par **région** ;
9. **valide la fiabilité du modèle de prévision** (backtesting : entraîné sur
   2024-2025, testé sur 2026).

Le dashboard s'organise en **7 onglets** : le premier (**Saisie / Import**) sert
à charger chaque mois le fichier de réalisations ; les six suivants présentent
les différentes analyses (tableau mensuel, suivi cumulé, sous-catégories,
comparaison des catégories, prévision & alertes, analyse régionale).

## Stack technique

- **Python 3.14** (environnement virtuel `venv`)
- **pandas / numpy** — manipulation des données
- **Plotly** — graphiques interactifs
- **Streamlit** — dashboard web
- **Prophet** — prévision de séries temporelles
- **scipy** — calcul de probabilité (loi normale)

## Installation

```bash
# 1. Créer et activer l'environnement virtuel (Windows)
python -m venv venv
venv\Scripts\activate

# 2a. Installer les librairies du dashboard
pip install -r requirements.txt

# 2b. (optionnel) Pour régénérer les prévisions et probabilités : ajouter Prophet/scipy
pip install -r requirements-dev.txt
```

> Le dashboard (`app.py`) ne lit que des fichiers CSV : il n'a besoin que de
> `requirements.txt`. Prophet et scipy (dans `requirements-dev.txt`) ne servent
> qu'aux scripts `forecast.py` et `prediction_atteinte.py`.

## Utilisation

### Lancer le dashboard (interface principale)

```bash
streamlit run app.py
```

### Régénérer les données de calcul (après modification des CSV sources)

Les scripts s'exécutent **dans cet ordre** (chacun produit un fichier que le
suivant peut utiliser) :

```bash
python forecast.py             # prévision Prophet        -> data/prevision.csv
python calcul_kpi.py           # KPI mensuels             -> data/kpi_mensuel.csv
python prediction_atteinte.py  # probabilité d'atteinte   -> data/atteinte_objectif.csv
python anomalies.py            # anomalies (z-score)      -> data/anomalies.csv
python validation_modele.py    # fiabilité du modèle      -> data/validation_modele.csv
```

Le dashboard relit automatiquement ces fichiers (bouton **Rerun** dans le navigateur).

## Tests

Des tests unitaires valident automatiquement les calculs de KPI (taux de
réalisation, protection contre la division par zéro). Pour les lancer :

```bash
pytest -v
```

## Structure du projet

```
tt_kpi/
├── data/
│   ├── ventes.csv              # ventes journalières (source)
│   ├── objectifs.csv           # objectifs mensuels par catégorie (source)
│   ├── kpi_mensuel.csv         # généré par calcul_kpi.py
│   ├── prevision.csv           # généré par forecast.py
│   ├── atteinte_objectif.csv   # généré par prediction_atteinte.py
│   ├── anomalies.csv           # généré par anomalies.py
│   └── validation_modele.csv   # généré par validation_modele.py
├── assets/
│   └── logo_tt.png             # logo affiché dans le dashboard
├── kpi.py                      # module partagé : calcul des KPI
├── decouverte.py               # aperçu des données
├── calcul_kpi.py               # calcul des KPI mensuels
├── forecast.py                 # prévision Prophet
├── prediction_atteinte.py      # probabilité d'atteinte de l'objectif annuel
├── anomalies.py                # détection des jours de vente anormaux
├── validation_modele.py        # validation (backtesting) du modèle de prévision
├── app.py                      # dashboard Streamlit (interface)
├── requirements.txt            # librairies à installer
└── README.md                   # ce fichier
```

## Modèle de données

**`data/ventes.csv`** — une ligne = ventes d'une sous-catégorie un jour donné :

| date | categorie | sous_categorie | quantite | region |
|------|-----------|----------------|----------|--------|
| 2026-01-01 | Internet Fixe | Rapido | 6 | Grand Tunis |

> C'est exactement le format attendu par l'onglet **Saisie / Import** : un
> modèle vierge est téléchargeable directement depuis le dashboard.

**`data/objectifs.csv`** — un objectif mensuel par catégorie :

| categorie | annee | mois | objectif_mensuel |
|-----------|-------|------|------------------|
| Internet Fixe | 2026 | 1 | 1309 |

> Les données actuelles sont **simulées** (démo) et couvrent 2024, 2025 et
> janvier→juin 2026. Les mois suivants sont ceux que le module de prévision estime.

## Note

Projet réalisé dans un cadre pédagogique. Les données sont simulées et ne
reflètent pas les chiffres réels de Tunisie Télécom.