import pandas as pd
from scipy.stats import norm

# ============================================================================
# Etape 7 (partie 1) : probabilite d'atteindre l'objectif ANNUEL
# ----------------------------------------------------------------------------
# Idee :
#   - Pour une annee, on additionne les 12 mois pour estimer le total annuel.
#   - Certains mois sont deja realises (ventes reelles connues) : aucune
#     incertitude dessus.
#   - Les autres mois viennent de la prevision Prophet : on connait la valeur
#     estimee (prevision) ET une fourchette (prevision_min / prevision_max)
#     qui traduit l'incertitude du modele.
#   - On combine le tout pour estimer : total annuel probable + incertitude,
#     puis on calcule la probabilite que ce total depasse l'objectif annuel.
# ============================================================================

# --- Chargement des donnees ---
ventes = pd.read_csv("data/ventes.csv")
objectifs = pd.read_csv("data/objectifs.csv")
prevision = pd.read_csv("data/prevision.csv")

ventes["date"] = pd.to_datetime(ventes["date"])
ventes["annee"] = ventes["date"].dt.year
ventes["mois"] = ventes["date"].dt.month

# --- Realise mensuel par categorie (comme dans calcul_kpi.py) ---
ventes_mensuelles = (
    ventes.groupby(["categorie", "annee", "mois"])["quantite"]
    .sum()
    .reset_index()
    .rename(columns={"quantite": "ventes_reelles"})
)

# --- Objectif ANNUEL = somme des 12 objectifs mensuels de l'annee ---
objectif_annuel = (
    objectifs.groupby(["categorie", "annee"])["objectif_mensuel"]
    .sum()
    .reset_index()
    .rename(columns={"objectif_mensuel": "objectif_annuel"})
)

# Prophet utilise par defaut un intervalle de confiance a 80% :
#   [prevision_min, prevision_max] contient la vraie valeur avec 80% de chance.
# Pour une loi normale, 80% central correspond a +/- 1.2816 ecart-type.
# On en deduit l'ecart-type d'un mois prevu a partir de la largeur de sa fourchette.
Z_80 = norm.ppf(0.90)  # ~1.2816 (0.90 car il reste 10% dans chaque queue)

resultats = []

# On analyse chaque couple (categorie, annee) present dans les objectifs.
for _, ligne in objectif_annuel.iterrows():
    categorie = ligne["categorie"]
    annee = ligne["annee"]
    cible = ligne["objectif_annuel"]

    # 1) Part deja REALISEE : somme des ventes reelles connues pour cette annee.
    #    (Pas d'incertitude : ces mois sont du passe.)
    realise = ventes_mensuelles[
        (ventes_mensuelles["categorie"] == categorie)
        & (ventes_mensuelles["annee"] == annee)
    ]
    mois_realises = set(realise["mois"])
    total_realise = realise["ventes_reelles"].sum()

    # 2) Part PREVUE : les mois de l'annee qui ne sont PAS encore realises,
    #    on va chercher leur valeur dans la prevision Prophet.
    prevision_annee = prevision[
        (prevision["categorie"] == categorie)
        & (prevision["annee"] == annee)
        & (~prevision["mois"].isin(mois_realises))
    ]

    total_prevu = prevision_annee["prevision"].sum()

    # Ecart-type de chaque mois prevu = (max - min) / (2 * 1.2816).
    # La variance d'une somme de mois independants = somme des variances,
    # donc l'ecart-type total = racine carree de la somme des variances.
    ecarts_types_mois = (
        prevision_annee["prevision_max"] - prevision_annee["prevision_min"]
    ) / (2 * Z_80)
    variance_totale = (ecarts_types_mois ** 2).sum()
    ecart_type_total = variance_totale ** 0.5

    # 3) Total annuel estime = realise (certain) + prevu (incertain)
    total_estime = total_realise + total_prevu

    # 4) Probabilite d'atteindre l'objectif :
    #    part de la "cloche" (loi normale centree sur total_estime) situee
    #    au-dessus de la cible. Si tous les mois sont deja realises, il n'y a
    #    plus d'incertitude -> reponse binaire (0% ou 100%).
    if ecart_type_total > 0:
        probabilite = 1 - norm.cdf(cible, loc=total_estime, scale=ecart_type_total)
    else:
        probabilite = 1.0 if total_estime >= cible else 0.0

    # Ecart restant a combler (positif = il manque des ventes, negatif = objectif deja depasse)
    ecart_a_combler = cible - total_estime

    resultats.append(
        {
            "categorie": categorie,
            "annee": annee,
            "realise_connu": round(total_realise),
            "prevu_restant": round(total_prevu),
            "total_estime": round(total_estime),
            "objectif_annuel": round(cible),
            "ecart_a_combler": round(ecart_a_combler),
            "taux_estime_pct": round(total_estime / cible * 100, 1) if cible != 0 else None,
            "probabilite_atteinte_pct": round(probabilite * 100, 1),
        }
    )

atteinte = pd.DataFrame(resultats).sort_values(["categorie", "annee"])

print("=== Probabilite d'atteindre l'objectif annuel ===")
print(atteinte.to_string(index=False))

# --- Diagnostic en langage clair (une phrase par ligne du tableau) ---
# On met en avant le message utile : la trajectoire (taux estime) et le nombre
# de ventes qu'il reste a faire, plutot que la seule probabilite brute.
print("\n=== Lecture des resultats ===")
for _, r in atteinte.iterrows():
    if r["ecart_a_combler"] <= 0:
        print(
            f"- {r['categorie']} {r['annee']} : objectif ATTEINT "
            f"({r['taux_estime_pct']} %), soit {abs(r['ecart_a_combler'])} ventes au-dela de la cible."
        )
    else:
        print(
            f"- {r['categorie']} {r['annee']} : trajectoire a {r['taux_estime_pct']} % de l'objectif "
            f"(proba {r['probabilite_atteinte_pct']} %). Il manque environ {r['ecart_a_combler']} ventes pour l'atteindre."
        )

atteinte.to_csv("data/atteinte_objectif.csv", index=False)
print("\nFichier genere : data/atteinte_objectif.csv")