import pandas as pd
from prophet import Prophet
from prophet.plot import plot_plotly

# Nombre de mois a prevoir : juillet 2026 -> decembre 2027 (18 mois),
# soit toute la periode ou l'on a des objectifs mais pas encore de ventes reelles.
NB_MOIS_PREVISION = 18

# --- Construction de la serie mensuelle par categorie ---
ventes = pd.read_csv("data/ventes.csv")
ventes["date"] = pd.to_datetime(ventes["date"])

# pd.Grouper(freq="MS") regroupe les dates par mois (Month Start),
# comme on le faisait avec annee/mois dans calcul_kpi.py, mais en gardant
# une vraie colonne date (necessaire pour Prophet).
ventes_mensuelles = (
    ventes.groupby([pd.Grouper(key="date", freq="MS"), "categorie"])["quantite"]
    .sum()
    .reset_index()
    .rename(columns={"quantite": "ventes_reelles"})
)

previsions = []

for categorie in ventes_mensuelles["categorie"].unique():
    # Prophet exige exactement deux colonnes : "ds" (la date) et "y" (la valeur a prevoir)
    serie = ventes_mensuelles.loc[
        ventes_mensuelles["categorie"] == categorie, ["date", "ventes_reelles"]
    ].rename(columns={"date": "ds", "ventes_reelles": "y"})

    # Entrainement du modele sur l'historique de cette categorie
    modele = Prophet()
    modele.fit(serie)

    # make_future_dataframe prolonge la serie de NB_MOIS_PREVISION mois
    # au-dela de la derniere date connue
    futur = modele.make_future_dataframe(periods=NB_MOIS_PREVISION, freq="MS")
    prevision = modele.predict(futur)

    prevision["categorie"] = categorie
    previsions.append(prevision[["ds", "categorie", "yhat", "yhat_lower", "yhat_upper"]])

    # Graphique interactif : ligne "yhat" = prevision, zone grisee = intervalle
    # de confiance (yhat_lower a yhat_upper), points = ventes reelles connues
    figure = plot_plotly(modele, prevision)
    figure.update_layout(title=f"Prevision des ventes - {categorie}")
    figure.show()

# --- Sauvegarde du resultat ---
prevision_totale = pd.concat(previsions).sort_values(["categorie", "ds"])
prevision_totale = prevision_totale.rename(
    columns={"yhat": "prevision", "yhat_lower": "prevision_min", "yhat_upper": "prevision_max"}
)
prevision_totale["annee"] = prevision_totale["ds"].dt.year
prevision_totale["mois"] = prevision_totale["ds"].dt.month

prevision_totale.to_csv("data/prevision.csv", index=False)

print(prevision_totale.tail(20))
print("\nFichier genere : data/prevision.csv")