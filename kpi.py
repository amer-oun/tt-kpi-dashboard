"""Module partage pour le calcul des KPI.

Ce fichier centralise la logique de calcul afin qu'elle ne soit ecrite qu'UNE
seule fois. calcul_kpi.py (script en ligne de commande) et app.py (dashboard)
importent tous les deux ces fonctions : si un jour on change la formule du taux
d'atteinte, il n'y a qu'un seul endroit a modifier. C'est le principe du code
"modulaire" (convention du projet).
"""

import pandas as pd


def preparer_ventes(ventes):
    """Prepare le tableau des ventes pour l'analyse.

    - convertit la colonne 'date' (texte) en vraie date ;
    - ajoute deux colonnes 'annee' et 'mois' (utiles pour regrouper).

    On travaille sur une COPIE pour ne pas modifier le tableau d'origine
    de facon inattendue chez l'appelant.
    """
    ventes = ventes.copy()
    ventes["date"] = pd.to_datetime(ventes["date"])
    ventes["annee"] = ventes["date"].dt.year
    ventes["mois"] = ventes["date"].dt.month
    return ventes


def calculer_kpi(ventes, objectifs):
    """Calcule le KPI mensuel par categorie (ventes reelles vs objectif).

    'ventes' doit deja contenir les colonnes 'annee' et 'mois'
    (utiliser preparer_ventes() au prealable).

    Renvoie un DataFrame avec, par categorie/annee/mois :
        ventes_reelles, objectif_mensuel, taux_atteinte_pct, ecart.
    """
    # Cumul mensuel des ventes journalieres, par categorie
    ventes_mensuelles = (
        ventes.groupby(["categorie", "annee", "mois"])["quantite"]
        .sum()
        .reset_index()
        .rename(columns={"quantite": "ventes_reelles"})
    )

    # On associe chaque mois a son objectif (jointure "inner" : on ne garde
    # que les mois presents des DEUX cotes, reel ET objectif).
    kpi = ventes_mensuelles.merge(objectifs, on=["categorie", "annee", "mois"], how="inner")

    # Taux de realisation = ventes / objectif (en %), avec protection contre
    # la division par zero : si l'objectif vaut 0, le taux reste indefini (None).
    kpi["taux_atteinte_pct"] = None
    objectif_valide = kpi["objectif_mensuel"] != 0
    kpi.loc[objectif_valide, "taux_atteinte_pct"] = (
        kpi.loc[objectif_valide, "ventes_reelles"] / kpi.loc[objectif_valide, "objectif_mensuel"] * 100
    ).round(1)

    # Ecart brut entre le realise et l'objectif
    kpi["ecart"] = kpi["ventes_reelles"] - kpi["objectif_mensuel"]

    return kpi.sort_values(["categorie", "annee", "mois"])