# -*- coding: utf-8 -*-
"""
Genere les FICHIERS DE REALISATIONS par region, a partir des ventes reelles.

Contexte (demande de l'encadrant professionnel) :
  - Les OBJECTIFS sont nationaux (objectifs.csv).
  - Les REALISATIONS (ventes reellement effectuees) sont des donnees PAR REGION.
Ce script part de data/ventes.csv (les realisations journalieres, deja munies
d'une colonne 'region') et produit un fichier de realisations agregees par
region, categorie, annee et mois :

  - data/realisations_par_region.csv  (donnees, meme format que les autres CSV)
  - Realisations_TT_par_region.xlsx   (classeur Excel a envoyer / presenter)

IMPORTANT : on ne modifie PAS ventes.csv. On ne fait que resumer les ventes.
Le total des realisations reste donc identique a celui des ventes.
"""

import pandas as pd

# 1) On lit les ventes reelles (= les realisations journalieres)
ventes = pd.read_csv("data/ventes.csv")

# 2) On ajoute l'annee et le mois a partir de la date
ventes["date"] = pd.to_datetime(ventes["date"])
ventes["annee"] = ventes["date"].dt.year
ventes["mois"] = ventes["date"].dt.month

# 3) Agregation : realisation mensuelle par region + categorie
#    (somme des quantites vendues sur le mois)
realisations = (
    ventes.groupby(["annee", "mois", "region", "categorie"], as_index=False)["quantite"]
    .sum()
    .rename(columns={"quantite": "realisation"})
    .sort_values(["annee", "mois", "region", "categorie"])
)

# 4) Sauvegarde du fichier de donnees (CSV)
realisations.to_csv("data/realisations_par_region.csv", index=False)

# 5) Tableaux de synthese pour le classeur Excel
#    a) Realisation totale par region et par annee
synthese_region = (
    ventes.groupby(["annee", "region"], as_index=False)["quantite"]
    .sum()
    .rename(columns={"quantite": "realisation"})
    .pivot(index="region", columns="annee", values="realisation")
    .fillna(0)
    .astype(int)
)

#    b) Realisation par region et par categorie (toutes annees confondues)
synthese_cat = (
    ventes.groupby(["region", "categorie"], as_index=False)["quantite"]
    .sum()
    .rename(columns={"quantite": "realisation"})
    .pivot(index="region", columns="categorie", values="realisation")
    .fillna(0)
    .astype(int)
)

# 6) Ecriture du classeur Excel (3 feuilles)
with pd.ExcelWriter("Realisations_TT_par_region.xlsx", engine="openpyxl") as writer:
    realisations.to_excel(writer, sheet_name="Realisations detaillees", index=False)
    synthese_region.to_excel(writer, sheet_name="Total par region-annee")
    synthese_cat.to_excel(writer, sheet_name="Par region-categorie")

# 7) Verifications affichees dans la console
total_ventes = int(ventes["quantite"].sum())
total_realis = int(realisations["realisation"].sum())
print("=== Fichiers de realisations generes ===")
print("- data/realisations_par_region.csv")
print("- Realisations_TT_par_region.xlsx")
print()
print("Lignes de realisations (region x categorie x mois) :", len(realisations))
print("Total des ventes (ventes.csv)      :", total_ventes)
print("Total des realisations (resume)    :", total_realis)
print("=> Coherence (aucun chiffre perdu) :", total_ventes == total_realis)
print()
print("Realisation totale par region et par annee :")
print(synthese_region)