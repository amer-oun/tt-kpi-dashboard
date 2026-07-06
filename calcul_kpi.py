import pandas as pd

# On importe la logique de calcul depuis le module partage kpi.py
# (plus besoin de recopier le calcul : il est ecrit une seule fois la-bas).
from kpi import preparer_ventes, calculer_kpi

# On charge les deux fichiers sources
ventes = pd.read_csv("data/ventes.csv")
objectifs = pd.read_csv("data/objectifs.csv")

# Preparation (dates + annee/mois) puis calcul des KPI mensuels
ventes = preparer_ventes(ventes)
kpi = calculer_kpi(ventes, objectifs)

print("=== KPI mensuel (ventes reelles vs objectif) ===")
print(kpi)

# On sauvegarde le resultat pour pouvoir le reutiliser (dashboard, etc.)
kpi.to_csv("data/kpi_mensuel.csv", index=False)
print("\nFichier genere : data/kpi_mensuel.csv")