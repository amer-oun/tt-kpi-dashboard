import pandas as pd

# ============================================================================
# Etape 7 (partie 2) : detection des jours de vente ANORMAUX (methode z-score)
# ----------------------------------------------------------------------------
# Idee :
#   - Pour chaque sous-categorie, on calcule la moyenne et l'ecart-type des
#     ventes journalieres (le comportement "habituel").
#   - Le z-score d'un jour mesure de combien d'ecarts-types ce jour s'ecarte
#     de la moyenne :  z = (quantite - moyenne) / ecart_type
#   - Si |z| depasse un seuil (ici 3), le jour est considere comme anormal :
#     pic inhabituel (z tres positif) ou chute suspecte (z tres negatif).
# ============================================================================

SEUIL_Z = 3  # au-dela de 3 ecarts-types, on considere le jour anormal

# --- Chargement des ventes journalieres ---
ventes = pd.read_csv("data/ventes.csv")
ventes["date"] = pd.to_datetime(ventes["date"])

# --- Calcul du z-score PAR sous-categorie ---
# groupby(...).transform(...) renvoie une valeur PAR LIGNE (meme longueur que
# le tableau d'origine), contrairement a .sum() qui regroupe. Cela permet de
# rattacher a chaque jour la moyenne / l'ecart-type de SA sous-categorie.
moyenne = ventes.groupby("sous_categorie")["quantite"].transform("mean")
ecart_type = ventes.groupby("sous_categorie")["quantite"].transform("std")

# Protection : si une sous-categorie a un ecart-type de 0 (ventes toujours
# identiques), on evite la division par zero -> z-score mis a 0 (aucun ecart).
ventes["z_score"] = 0.0
ecart_type_valide = ecart_type != 0
ventes.loc[ecart_type_valide, "z_score"] = (
    (ventes.loc[ecart_type_valide, "quantite"] - moyenne[ecart_type_valide])
    / ecart_type[ecart_type_valide]
).round(2)

# --- On isole les jours anormaux ---
anomalies = ventes[ventes["z_score"].abs() > SEUIL_Z].copy()

# On qualifie le type d'anomalie pour une lecture plus claire
anomalies["type_anomalie"] = anomalies["z_score"].apply(
    lambda z: "Pic (vente inhabituellement haute)" if z > 0 else "Chute (vente inhabituellement basse)"
)

anomalies = anomalies.sort_values("z_score", key=lambda col: col.abs(), ascending=False)

# --- Affichage ---
print(f"Seuil utilise : |z| > {SEUIL_Z}")
print(f"Nombre de jours analyses  : {len(ventes)}")
print(f"Nombre d'anomalies trouvees : {len(anomalies)}")
print("\n=== Jours de vente anormaux (tries du plus extreme au moins extreme) ===")

colonnes_affichees = ["date", "categorie", "sous_categorie", "quantite", "z_score", "type_anomalie"]
if len(anomalies) > 0:
    print(anomalies[colonnes_affichees].to_string(index=False))
else:
    print("Aucune anomalie detectee avec ce seuil.")

# --- Sauvegarde ---
anomalies[colonnes_affichees].to_csv("data/anomalies.csv", index=False)
print("\nFichier genere : data/anomalies.csv")