"""Validation retrospective du modele de prevision (backtesting).

Idee : au lieu de croire aveuglement Prophet, on VERIFIE sa fiabilite sur une
periode dont on connait deja les vraies ventes.

Methode (train-test split dans le temps) :
  1. On entraine Prophet UNIQUEMENT sur 2024 + 2025 (le modele ne "voit" pas 2026).
  2. On lui demande de prevoir janvier -> juin 2026.
  3. On compare sa prevision aux VRAIES ventes de janvier -> juin 2026.
  4. On mesure l'erreur avec deux indicateurs simples :
       - MAE  : erreur absolue moyenne  -> "il se trompe de X ventes par mois"
       - MAPE : erreur en pourcentage   -> "il se trompe de Y % en moyenne"

Si l'erreur est faible sur une periode que le modele n'a jamais vue, on a une
PREUVE CHIFFREE que la prevision est credible. C'est l'argument a donner au jury.

Genere : data/validation_modele.csv (reel vs prevu, mois par mois).
"""

import pandas as pd
from prophet import Prophet

# --- Frontiere entre entrainement et test ---
# Le modele apprend sur tout ce qui est AVANT cette date, et on teste APRES.
DATE_LIMITE_ENTRAINEMENT = "2025-12-31"

# --- 1. Construction de la serie mensuelle par categorie ---
ventes = pd.read_csv("data/ventes.csv")
ventes["date"] = pd.to_datetime(ventes["date"])

# On regroupe les ventes journalieres en totaux mensuels (freq="MS" = debut de mois)
ventes_mensuelles = (
    ventes.groupby([pd.Grouper(key="date", freq="MS"), "categorie"])["quantite"]
    .sum()
    .reset_index()
    .rename(columns={"quantite": "ventes_reelles"})
)

resultats = []

for categorie in ventes_mensuelles["categorie"].unique():
    serie = ventes_mensuelles[ventes_mensuelles["categorie"] == categorie]

    # --- 2. Separation train / test ---
    # train = ce que le modele a le droit de voir (2024 + 2025)
    # test  = ce qu'on lui cache et qu'on utilisera pour le juger (2026)
    train = serie[serie["date"] <= DATE_LIMITE_ENTRAINEMENT]
    test = serie[serie["date"] > DATE_LIMITE_ENTRAINEMENT]

    # Prophet exige deux colonnes nommees "ds" (date) et "y" (valeur a prevoir)
    train_prophet = train[["date", "ventes_reelles"]].rename(
        columns={"date": "ds", "ventes_reelles": "y"}
    )

    # --- 3. Entrainement puis prevision des mois de test ---
    modele = Prophet()
    modele.fit(train_prophet)

    # On prolonge de 6 mois (janvier -> juin 2026) et on predit
    futur = modele.make_future_dataframe(periods=len(test), freq="MS")
    prevision = modele.predict(futur)

    # On ne garde que les mois de test pour la comparaison
    prevision_test = prevision[prevision["ds"] > DATE_LIMITE_ENTRAINEMENT][["ds", "yhat"]]

    # On rassemble cote a cote : vraie valeur (test) et valeur prevue (yhat)
    comparaison = test.merge(prevision_test, left_on="date", right_on="ds")
    comparaison = comparaison.rename(columns={"yhat": "ventes_prevues"})
    comparaison["categorie"] = categorie

    # Erreur mois par mois (en valeur absolue et en pourcentage)
    comparaison["erreur"] = comparaison["ventes_prevues"] - comparaison["ventes_reelles"]
    comparaison["erreur_abs"] = comparaison["erreur"].abs()
    comparaison["erreur_pct"] = (
        comparaison["erreur_abs"] / comparaison["ventes_reelles"] * 100
    ).round(1)

    resultats.append(
        comparaison[
            ["categorie", "date", "ventes_reelles", "ventes_prevues", "erreur", "erreur_abs", "erreur_pct"]
        ]
    )

# --- 4. Rassemblement et calcul des indicateurs de qualite ---
validation = pd.concat(resultats).sort_values(["categorie", "date"])
# Arrondis pour un affichage propre
validation["ventes_prevues"] = validation["ventes_prevues"].round(0)
validation["erreur"] = validation["erreur"].round(0)
validation["erreur_abs"] = validation["erreur_abs"].round(0)

validation.to_csv("data/validation_modele.csv", index=False)

# --- 5. Affichage d'un bilan lisible par categorie ---
print("=== Validation du modele : entraine sur 2024-2025, teste sur jan-juin 2026 ===\n")
for categorie in validation["categorie"].unique():
    bloc = validation[validation["categorie"] == categorie]
    mae = bloc["erreur_abs"].mean()          # erreur moyenne en nombre de ventes
    mape = bloc["erreur_pct"].mean()         # erreur moyenne en pourcentage
    print(f"--- {categorie} ---")
    print(bloc[["date", "ventes_reelles", "ventes_prevues", "erreur", "erreur_pct"]].to_string(index=False))
    print(f"  MAE  (erreur moyenne)   : {mae:.0f} ventes / mois")
    print(f"  MAPE (erreur moyenne %) : {mape:.1f} %")
    print(f"  Fiabilite estimee       : {100 - mape:.1f} %\n")

print("Fichier genere : data/validation_modele.csv")