import pandas as pd
import numpy as np

# ============================================================================
# Ajoute une colonne "region" au fichier des ventes (dimension geographique).
# IMPORTANT : on N'AJOUTE qu'une colonne. Les quantites de vente ne changent
# pas -> les totaux (KPI, previsions, anomalies) restent identiques.
# ============================================================================

# Principales regions de Tunisie, avec un poids (part de marche approximative).
# Grand Tunis pese le plus, Kairouan le moins -> repartition realiste.
REGIONS = ["Grand Tunis", "Sfax", "Sousse", "Nabeul", "Bizerte", "Gabes", "Kairouan"]
POIDS = [0.30, 0.16, 0.15, 0.12, 0.10, 0.09, 0.08]  # somme = 1.00

ventes = pd.read_csv("data/ventes.csv")

# Total AVANT, pour verifier qu'on ne change aucun chiffre
total_avant = ventes["quantite"].sum()

# Generateur aleatoire avec une graine fixe (42) : le tirage est reproductible,
# donc on obtient toujours la meme repartition regionale.
generateur = np.random.default_rng(42)
ventes["region"] = generateur.choice(REGIONS, size=len(ventes), p=POIDS)

# Total APRES : doit etre exactement le meme (on n'a fait qu'ajouter une etiquette)
total_apres = ventes["quantite"].sum()

ventes.to_csv("data/ventes.csv", index=False)

print("=== Colonne 'region' ajoutee a data/ventes.csv ===")
print(ventes.head())
print("\nRepartition des lignes par region :")
print(ventes["region"].value_counts())
print(f"\nTotal des ventes AVANT : {total_avant}")
print(f"Total des ventes APRES : {total_apres}")
print("=> identique :", total_avant == total_apres)