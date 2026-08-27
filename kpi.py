"""Module partage pour le calcul des KPI.

Ce fichier centralise la logique de calcul afin qu'elle ne soit ecrite qu'UNE
seule fois. calcul_kpi.py (script en ligne de commande) et app.py (dashboard)
importent tous les deux ces fonctions : si un jour on change la formule du taux
d'atteinte, il n'y a qu'un seul endroit a modifier. C'est le principe du code
"modulaire" (convention du projet).
"""

import calendar

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


# Part minimale des journees d'un mois en dessous de laquelle on considere
# que le mois n'est pas exploitable. 0.5 = la moitie du mois.
PART_MINIMALE_DU_MOIS = 0.5


def separer_mois_complets(ventes, part_minimale=PART_MINIMALE_DU_MOIS):
    """Ecarte les mois dont les donnees sont manifestement partielles.

    POURQUOI : un objectif est defini pour un mois ENTIER. Si l'on importe un
    fichier ne couvrant que deux journees, le mois correspondant sera malgre
    tout compare a l'objectif complet, et le taux de realisation s'effondrera
    sans qu'il y ait le moindre retard reel.

    On compte donc, pour chaque mois, le nombre de journees effectivement
    presentes, et on le rapporte au nombre de journees que compte ce mois au
    calendrier. En dessous du seuil, le mois est ecarte du calcul.

    'ventes' doit deja contenir les colonnes 'annee' et 'mois'
    (utiliser preparer_ventes() au prealable).

    Renvoie un couple (ventes_retenues, mois_ecartes), ou mois_ecartes est une
    liste de dictionnaires {annee, mois, jours_presents, jours_du_mois}.
    """
    if ventes.empty:
        return ventes, []

    # Nombre de journees DISTINCTES presentes pour chaque couple (annee, mois)
    jours_presents = ventes.groupby(["annee", "mois"])["date"].nunique()

    ecartes = []
    for (annee, mois), presents in jours_presents.items():
        # calendar.monthrange renvoie (jour de la semaine du 1er, nb de jours)
        jours_du_mois = calendar.monthrange(int(annee), int(mois))[1]
        if presents / jours_du_mois < part_minimale:
            ecartes.append({
                "annee": int(annee),
                "mois": int(mois),
                "jours_presents": int(presents),
                "jours_du_mois": int(jours_du_mois),
            })

    if not ecartes:
        return ventes, []

    a_ecarter = {(d["annee"], d["mois"]) for d in ecartes}
    garder = ~ventes.apply(
        lambda ligne: (ligne["annee"], ligne["mois"]) in a_ecarter, axis=1
    )
    return ventes[garder], ecartes


# ============================================================================
#  Du constat a la recommandation
# ============================================================================
# Les fonctions ci-dessus disent OU L'ON EN EST. Celles qui suivent disent OU
# AGIR : c'est la difference entre un tableau de bord, qui informe, et un outil
# d'aide a la decision, qui oriente.

def repartir_effort(ventes, categorie, annee, manque, mois_restants):
    """Repartit un effort de rattrapage entre les regions.

    PRINCIPE : on ne demande pas le meme effort a une region qui pese 31 % des
    ventes et a une autre qui en pese 8 %. L'effort est donc reparti au prorata
    du poids de chaque region dans la categorie, sur l'annee en cours.

    'manque' est le nombre total de ventes a rattraper, 'mois_restants' le
    nombre de mois pour y parvenir.

    Renvoie un DataFrame trie par poids decroissant :
        region, poids_pct, effort_total, effort_mensuel
    Renvoie un DataFrame vide si le calcul n'a pas de sens.
    """
    if manque <= 0 or mois_restants <= 0:
        return pd.DataFrame(columns=["region", "poids_pct", "effort_total",
                                     "effort_mensuel"])

    lignes = ventes[(ventes["annee"] == annee) & (ventes["categorie"] == categorie)]
    if lignes.empty or lignes["quantite"].sum() == 0:
        return pd.DataFrame(columns=["region", "poids_pct", "effort_total",
                                     "effort_mensuel"])

    poids = lignes.groupby("region")["quantite"].sum()
    poids = (poids / poids.sum()).sort_values(ascending=False)

    resultat = pd.DataFrame({
        "region": poids.index,
        "poids_pct": (poids.values * 100).round(1),
        "effort_total": (poids.values * manque).round().astype(int),
        # -(-a // b) : division arrondie vers le HAUT, pour ne pas
        # sous-estimer l'effort demande.
        "effort_mensuel": [-(-int(round(p * manque)) // mois_restants)
                           for p in poids.values],
    })
    return resultat.reset_index(drop=True)


def evolution_des_parts(ventes, categorie, annee, mois_reference,
                        dimension="sous_categorie", jours_minimum=15):
    """Compare la part de chaque valeur d'une dimension au dernier mois connu
    a sa part moyenne depuis le debut de l'annee.

    POURQUOI LES PARTS ET NON LES VOLUMES : en fin d'annee, tout baisse en
    volume. Ce qui interesse le responsable, c'est ce qui baisse PLUS QUE LE
    RESTE, donc ce qui perd du terrain relativement aux autres.

    'dimension' vaut 'sous_categorie' (quelle offre decroche) ou 'region'
    (quelle region decroche).

    'jours_minimum' protege contre les echantillons trop minces : deux ou trois
    lignes suffiraient a produire une variation spectaculaire mais denuee de
    sens.

    Renvoie une Series triee du plus fort recul a la plus forte progression,
    exprimee en pourcentage. Vide si le calcul n'est pas possible.
    """
    vide = pd.Series(dtype=float)

    lignes = ventes[(ventes["annee"] == annee) & (ventes["categorie"] == categorie)]
    if lignes.empty or lignes["quantite"].sum() == 0:
        return vide

    part_moyenne = lignes.groupby(dimension)["quantite"].sum() / lignes["quantite"].sum()

    dernier = lignes[lignes["mois"] == mois_reference]
    if dernier.empty or dernier["quantite"].sum() == 0:
        return vide
    if dernier["date"].nunique() < jours_minimum:
        return vide

    part_dernier = dernier.groupby(dimension)["quantite"].sum() / dernier["quantite"].sum()

    # On ne divise que par des parts moyennes non nulles
    part_moyenne = part_moyenne[part_moyenne > 0]
    evolution = ((part_dernier - part_moyenne) / part_moyenne * 100).dropna()
    return evolution.sort_values()


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