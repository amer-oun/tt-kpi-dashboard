"""Tests unitaires du module kpi.py.

Un test = un exemple dont on connait deja la reponse. pytest execute le code
et verifie tout seul que le resultat est le bon. Si un jour on casse le calcul
sans le vouloir, le test echoue et nous previent.

On suit le schema AAA :
  - Arrange : on prepare les donnees d'entree ;
  - Act     : on appelle la fonction a tester ;
  - Assert  : on verifie que le resultat est celui attendu.

Lancer les tests :  pytest -v
"""

import pandas as pd

from kpi import (preparer_ventes, calculer_kpi, separer_mois_complets,
                 repartir_effort, evolution_des_parts)


def test_preparer_ventes_ajoute_annee_et_mois():
    """preparer_ventes doit extraire l'annee et le mois depuis la date."""
    # Arrange
    ventes = pd.DataFrame(
        {
            "date": ["2026-01-15"],
            "categorie": ["Mobile"],
            "sous_categorie": ["Data"],
            "quantite": [5],
        }
    )
    # Act
    resultat = preparer_ventes(ventes)
    # Assert
    assert resultat.loc[0, "annee"] == 2026
    assert resultat.loc[0, "mois"] == 1


def test_calculer_kpi_taux_de_realisation():
    """1367 ventes pour un objectif de 1309 doivent donner un taux de 104.4 %."""
    # Arrange : deux jours de ventes (700 + 667 = 1367) pour janvier 2026
    ventes = preparer_ventes(
        pd.DataFrame(
            {
                "date": ["2026-01-05", "2026-01-20"],
                "categorie": ["Internet Fixe", "Internet Fixe"],
                "sous_categorie": ["ADSL", "Rapido"],
                "quantite": [700, 667],
            }
        )
    )
    objectifs = pd.DataFrame(
        {
            "categorie": ["Internet Fixe"],
            "annee": [2026],
            "mois": [1],
            "objectif_mensuel": [1309],
        }
    )
    # Act
    kpi = calculer_kpi(ventes, objectifs)
    ligne = kpi.iloc[0]
    # Assert
    assert ligne["ventes_reelles"] == 1367
    assert ligne["taux_atteinte_pct"] == 104.4
    assert ligne["ecart"] == 58


def test_calculer_kpi_protege_division_par_zero():
    """Si l'objectif vaut 0, le taux doit rester indefini (pas de plantage)."""
    # Arrange : un objectif a 0 (cas piege)
    ventes = preparer_ventes(
        pd.DataFrame(
            {
                "date": ["2026-02-10"],
                "categorie": ["Mobile"],
                "sous_categorie": ["Data"],
                "quantite": [50],
            }
        )
    )
    objectifs = pd.DataFrame(
        {
            "categorie": ["Mobile"],
            "annee": [2026],
            "mois": [2],
            "objectif_mensuel": [0],
        }
    )
    # Act
    kpi = calculer_kpi(ventes, objectifs)
    # Assert : le taux n'est pas calcule (None/NaN), et le code n'a pas plante
    assert pd.isna(kpi.iloc[0]["taux_atteinte_pct"])


def test_calculer_kpi_ignore_mois_sans_objectif():
    """Un mois de ventes sans objectif correspondant est ecarte (jointure inner)."""
    # Arrange : des ventes en mars 2026, mais aucun objectif pour mars
    ventes = preparer_ventes(
        pd.DataFrame(
            {
                "date": ["2026-03-01"],
                "categorie": ["Mobile"],
                "sous_categorie": ["Data"],
                "quantite": [100],
            }
        )
    )
    objectifs = pd.DataFrame(
        {
            "categorie": ["Mobile"],
            "annee": [2026],
            "mois": [1],  # objectif pour janvier, pas mars
            "objectif_mensuel": [500],
        }
    )
    # Act
    kpi = calculer_kpi(ventes, objectifs)
    # Assert : aucune ligne (les ventes de mars n'ont pas d'objectif)
    assert len(kpi) == 0


# ============================================================================
#  Detection des mois incomplets
# ============================================================================
def _ventes_du_mois(annee, mois, nb_jours, quantite=10):
    """Fabrique nb_jours de ventes consecutives pour un mois donne."""
    return pd.DataFrame({
        "date": [f"{annee}-{mois:02d}-{jour:02d}" for jour in range(1, nb_jours + 1)],
        "categorie": ["Mobile"] * nb_jours,
        "sous_categorie": ["Data"] * nb_jours,
        "quantite": [quantite] * nb_jours,
        "region": ["Sfax"] * nb_jours,
    })


def test_un_mois_complet_est_conserve():
    """Un mois couvrant toutes ses journees doit etre garde tel quel."""
    # Arrange : janvier 2026 en entier (31 jours)
    ventes = preparer_ventes(_ventes_du_mois(2026, 1, 31))
    # Act
    retenues, ecartes = separer_mois_complets(ventes)
    # Assert
    assert len(retenues) == 31
    assert ecartes == []


def test_un_mois_de_deux_journees_est_ecarte():
    """C'est le cas du modele vierge reimporte : 2 lignes ne font pas un mois.

    Sans cette protection, ces deux journees seraient comparees a l'objectif
    mensuel ENTIER et feraient apparaitre un retard fictif.
    """
    # Arrange : janvier complet + un juillet de 2 journees seulement
    ventes = pd.concat([_ventes_du_mois(2026, 1, 31), _ventes_du_mois(2026, 7, 2)])
    ventes = preparer_ventes(ventes)
    # Act
    retenues, ecartes = separer_mois_complets(ventes)
    # Assert : juillet a disparu, janvier est intact
    assert set(retenues["mois"]) == {1}
    assert len(ecartes) == 1
    assert ecartes[0]["mois"] == 7
    assert ecartes[0]["jours_presents"] == 2
    assert ecartes[0]["jours_du_mois"] == 31


def test_le_taux_n_est_pas_fausse_par_un_mois_partiel():
    """Verification de bout en bout : le taux doit rester celui du mois complet."""
    # Arrange : janvier complet (31 x 10 = 310 ventes) + juillet partiel
    ventes = pd.concat([_ventes_du_mois(2026, 1, 31), _ventes_du_mois(2026, 7, 2)])
    ventes = preparer_ventes(ventes)
    objectifs = pd.DataFrame({
        "categorie": ["Mobile", "Mobile"],
        "annee": [2026, 2026],
        "mois": [1, 7],
        "objectif_mensuel": [310, 310],
    })

    # Act : avec la protection
    retenues, _ = separer_mois_complets(ventes)
    kpi = calculer_kpi(retenues, objectifs)

    # Assert : un seul mois retenu, a 100 %
    assert len(kpi) == 1
    assert kpi.iloc[0]["taux_atteinte_pct"] == 100.0


def test_un_mois_a_moitie_rempli_est_conserve():
    """Le seuil est la moitie du mois : 16 jours sur 31 doivent passer."""
    ventes = preparer_ventes(_ventes_du_mois(2026, 1, 16))
    retenues, ecartes = separer_mois_complets(ventes)
    assert ecartes == []
    assert len(retenues) == 16


# ============================================================================
#  Du constat a la recommandation
# ============================================================================
def _ventes_par_region(regions_et_quantites, annee=2026, mois=1, nb_jours=20):
    """Fabrique des ventes reparties entre plusieurs regions.

    regions_et_quantites : dictionnaire {region: quantite par jour}.
    """
    lignes = []
    for jour in range(1, nb_jours + 1):
        for region, quantite in regions_et_quantites.items():
            lignes.append({
                "date": f"{annee}-{mois:02d}-{jour:02d}",
                "categorie": "Internet Fixe",
                "sous_categorie": "ADSL",
                "quantite": quantite,
                "region": region,
            })
    return preparer_ventes(pd.DataFrame(lignes))


def test_l_effort_est_reparti_au_prorata_du_poids_des_regions():
    """Une region qui pese 75 % des ventes doit porter 75 % de l'effort."""
    # Arrange : Sfax vend trois fois plus que Gabes (75 % / 25 %)
    ventes = _ventes_par_region({"Sfax": 30, "Gabes": 10})

    # Act : 400 ventes a rattraper sur 4 mois
    effort = repartir_effort(ventes, "Internet Fixe", 2026, 400, 4)

    # Assert
    assert list(effort["region"]) == ["Sfax", "Gabes"]      # trie par poids
    assert effort.loc[0, "poids_pct"] == 75.0
    assert effort.loc[1, "poids_pct"] == 25.0
    assert effort.loc[0, "effort_total"] == 300
    assert effort.loc[1, "effort_total"] == 100
    assert effort.loc[0, "effort_mensuel"] == 75            # 300 / 4
    assert effort.loc[1, "effort_mensuel"] == 25            # 100 / 4


def test_l_effort_mensuel_est_arrondi_vers_le_haut():
    """On ne doit jamais sous-estimer l'effort a fournir.

    10 ventes a rattraper en 3 mois font 3,33 par mois : on annonce 4, pas 3.
    """
    ventes = _ventes_par_region({"Sfax": 10})
    effort = repartir_effort(ventes, "Internet Fixe", 2026, 10, 3)
    assert effort.loc[0, "effort_total"] == 10
    assert effort.loc[0, "effort_mensuel"] == 4


def test_aucun_effort_a_repartir_si_l_objectif_est_atteint():
    """Un manque nul ou negatif ne donne aucune recommandation."""
    ventes = _ventes_par_region({"Sfax": 10, "Gabes": 10})
    assert repartir_effort(ventes, "Internet Fixe", 2026, 0, 6).empty
    assert repartir_effort(ventes, "Internet Fixe", 2026, -50, 6).empty


def test_aucun_effort_a_repartir_si_l_annee_est_terminee():
    """Sans mois restant, l'ecart ne peut plus etre rattrape."""
    ventes = _ventes_par_region({"Sfax": 10})
    assert repartir_effort(ventes, "Internet Fixe", 2026, 100, 0).empty


def test_l_evolution_des_parts_repere_ce_qui_decroche():
    """Une offre dont la part recule doit apparaitre en tete du classement."""
    # Arrange : en janvier, ADSL et FO se partagent les ventes a parts egales ;
    # en fevrier, ADSL s'effondre.
    lignes = []
    for jour in range(1, 21):
        lignes.append({"date": f"2026-01-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "ADSL", "quantite": 10, "region": "Sfax"})
        lignes.append({"date": f"2026-01-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "FO", "quantite": 10, "region": "Sfax"})
    for jour in range(1, 21):
        lignes.append({"date": f"2026-02-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "ADSL", "quantite": 2, "region": "Sfax"})
        lignes.append({"date": f"2026-02-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "FO", "quantite": 18, "region": "Sfax"})
    ventes = preparer_ventes(pd.DataFrame(lignes))

    # Act : on compare fevrier a la moyenne de l'annee
    evolution = evolution_des_parts(ventes, "Internet Fixe", 2026, 2,
                                    "sous_categorie")

    # Assert : ADSL arrive en tete (le plus fort recul) et FO progresse
    assert evolution.index[0] == "ADSL"
    assert evolution["ADSL"] < 0
    assert evolution["FO"] > 0


def test_l_evolution_ignore_un_echantillon_trop_mince():
    """Deux journees ne suffisent pas a conclure quoi que ce soit.

    Sans cette protection, un fichier partiel produirait des variations
    spectaculaires (+1900 %) et denuees de sens.
    """
    lignes = []
    for jour in range(1, 21):
        lignes.append({"date": f"2026-01-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "ADSL", "quantite": 10, "region": "Sfax"})
    # Fevrier ne compte que deux journees
    for jour in (1, 2):
        lignes.append({"date": f"2026-02-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "FO", "quantite": 50, "region": "Sfax"})
    ventes = preparer_ventes(pd.DataFrame(lignes))

    assert evolution_des_parts(ventes, "Internet Fixe", 2026, 2).empty


def test_l_evolution_fonctionne_aussi_sur_les_regions():
    """La meme fonction sert a reperer une offre ou une region qui decroche."""
    lignes = []
    for jour in range(1, 21):
        lignes.append({"date": f"2026-01-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "ADSL", "quantite": 10, "region": "Sfax"})
        lignes.append({"date": f"2026-01-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "ADSL", "quantite": 10, "region": "Gabes"})
    for jour in range(1, 21):
        lignes.append({"date": f"2026-02-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "ADSL", "quantite": 2, "region": "Sfax"})
        lignes.append({"date": f"2026-02-{jour:02d}", "categorie": "Internet Fixe",
                       "sous_categorie": "ADSL", "quantite": 18, "region": "Gabes"})
    ventes = preparer_ventes(pd.DataFrame(lignes))

    evolution = evolution_des_parts(ventes, "Internet Fixe", 2026, 2, "region")
    assert evolution.index[0] == "Sfax"
    assert evolution["Sfax"] < 0
