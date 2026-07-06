
import pandas as pd

# Charger les deux fichiers CSV dans des "DataFrames"
# (un DataFrame = un tableau de donnees en memoire, comme une feuille Excel)
ventes = pd.read_csv("data/ventes.csv")
objectifs = pd.read_csv("data/objectifs.csv")

# Afficher les 5 premieres lignes de chaque fichier
print("=== VENTES (5 premieres lignes) ===")
print(ventes.head())
print()
print("=== OBJECTIFS (5 premieres lignes) ===")
print(objectifs.head())
print()

# Quelques informations utiles
print("Nombre de lignes dans ventes :", len(ventes))
print()
print("Categories      :", list(ventes["categorie"].unique()))
print("Sous-categories :", list(ventes["sous_categorie"].unique()))