"""Tests unitaires du plan d'action (table `actions` de base_donnees.py).

Cette table est la seule que l'UTILISATEUR alimente lui-meme depuis
l'interface : les trois autres sont remplies par import ou par le code. Elle
porte le dialogue entre les deux acteurs du projet, et merite donc d'etre
verifiee avec le meme soin que l'authentification.

Chaque test travaille sur une base TEMPORAIRE : la vraie base n'est jamais
touchee.

Lancer les tests :  pytest -v
"""

import pandas as pd
import pytest

import base_donnees as bd


@pytest.fixture
def base_temporaire(tmp_path, monkeypatch):
    """Prepare une base vide et jetable, comme pour les autres tests."""
    ventes = pd.DataFrame(
        {
            "date": ["2026-01-05", "2026-01-06"],
            "categorie": ["Internet Fixe", "Mobile"],
            "sous_categorie": ["ADSL", "Data"],
            "quantite": [10, 20],
            "region": ["Sfax", "Grand Tunis"],
        }
    )
    objectifs = pd.DataFrame(
        {
            "categorie": ["Internet Fixe", "Mobile"],
            "annee": [2026, 2026],
            "mois": [1, 1],
            "objectif_mensuel": [100, 200],
        }
    )
    chemin_ventes = tmp_path / "ventes.csv"
    chemin_objectifs = tmp_path / "objectifs.csv"
    ventes.to_csv(chemin_ventes, index=False)
    objectifs.to_csv(chemin_objectifs, index=False)

    monkeypatch.setattr(bd, "CHEMIN_BASE", str(tmp_path / "test.db"))
    monkeypatch.setattr(bd, "CSV_VENTES", str(chemin_ventes))
    monkeypatch.setattr(bd, "CSV_OBJECTIFS", str(chemin_objectifs))

    bd.initialiser_base()
    yield


# ============================================================================
#  Creation d'une action
# ============================================================================
def test_une_action_creee_est_relue_avec_ses_informations(base_temporaire):
    """Ce qu'on enregistre doit se retrouver tel quel a la lecture."""
    # Arrange / Act
    identifiant = bd.creer_action(
        categorie="Internet Fixe", annee=2026, mois=6,
        texte="Renfort commercial a Bizerte sur l'offre ADSL",
        auteur="s.benammar", role_auteur="responsable_commercial",
        perimetre="Bizerte", echeance="2026-09-30",
    )

    # Assert
    actions = bd.lire_actions()
    assert len(actions) == 1
    action = actions[0]
    assert action["id"] == identifiant
    assert action["categorie"] == "Internet Fixe"
    assert action["perimetre"] == "Bizerte"
    assert action["echeance"] == "2026-09-30"
    assert action["auteur"] == "s.benammar"
    assert action["statut"] == "ouverte"          # statut par defaut
    assert action["reponse"] is None              # personne n'a encore repondu


def test_une_action_sans_texte_est_refusee(base_temporaire):
    """Une action vide n'aurait aucun sens : on la refuse a la source."""
    with pytest.raises(ValueError):
        bd.creer_action("Mobile", 2026, 6, "   ", "s.benammar",
                        "responsable_commercial")
    with pytest.raises(ValueError):
        bd.creer_action("Mobile", 2026, 6, "", "s.benammar",
                        "responsable_commercial")


# ============================================================================
#  Le dialogue : la direction repond
# ============================================================================
def test_la_direction_repond_a_une_action(base_temporaire):
    """C'est le coeur du dialogue : une action ouverte reçoit une reponse."""
    # Arrange
    identifiant = bd.creer_action(
        "Internet Fixe", 2026, 6, "Renfort commercial a Bizerte",
        "s.benammar", "responsable_commercial",
    )

    # Act
    ok = bd.repondre_action(identifiant, "Valide, budget accorde", "k.trabelsi")

    # Assert
    assert ok is True
    action = bd.lire_actions()[0]
    assert action["reponse"] == "Valide, budget accorde"
    assert action["auteur_reponse"] == "k.trabelsi"
    assert action["date_reponse"] is not None


def test_repondre_a_une_action_inexistante_ne_casse_rien(base_temporaire):
    """Repondre a une action supprimee entre-temps renvoie False, sans erreur."""
    assert bd.repondre_action(999, "Une reponse", "k.trabelsi") is False


def test_une_reponse_vide_est_refusee(base_temporaire):
    identifiant = bd.creer_action("Mobile", 2026, 6, "Une action",
                                  "s.benammar", "responsable_commercial")
    with pytest.raises(ValueError):
        bd.repondre_action(identifiant, "   ", "k.trabelsi")


# ============================================================================
#  Suivi : le statut evolue
# ============================================================================
def test_le_statut_evolue_de_ouverte_a_close(base_temporaire):
    """Une action se suit dans le temps : ouverte, en cours, puis close."""
    identifiant = bd.creer_action("Mobile", 2026, 6, "Campagne Data",
                                  "s.benammar", "responsable_commercial")

    assert bd.changer_statut_action(identifiant, "en cours") is True
    assert bd.lire_actions()[0]["statut"] == "en cours"

    assert bd.changer_statut_action(identifiant, "close") is True
    assert bd.lire_actions()[0]["statut"] == "close"


def test_un_statut_inconnu_est_refuse(base_temporaire):
    """Seuls les trois statuts prevus sont acceptes."""
    identifiant = bd.creer_action("Mobile", 2026, 6, "Campagne Data",
                                  "s.benammar", "responsable_commercial")
    with pytest.raises(ValueError):
        bd.changer_statut_action(identifiant, "annulee")


# ============================================================================
#  Filtrage
# ============================================================================
def test_les_actions_se_filtrent_par_categorie_annee_et_statut(base_temporaire):
    """Le tableau de bord n'affiche que les actions du perimetre consulte."""
    # Arrange : trois actions, de categories et statuts differents
    a1 = bd.creer_action("Internet Fixe", 2026, 6, "Action A",
                         "s.benammar", "responsable_commercial")
    bd.creer_action("Mobile", 2026, 6, "Action B",
                    "s.benammar", "responsable_commercial")
    bd.creer_action("Internet Fixe", 2027, 1, "Action C",
                    "s.benammar", "responsable_commercial")
    bd.changer_statut_action(a1, "close")

    # Assert
    assert len(bd.lire_actions()) == 3
    assert len(bd.lire_actions(categorie="Internet Fixe")) == 2
    assert len(bd.lire_actions(categorie="Internet Fixe", annee=2026)) == 1
    assert len(bd.lire_actions(statut="close")) == 1
    assert len(bd.lire_actions(statut="ouverte")) == 2


def test_une_tentative_d_injection_sql_dans_le_filtre_echoue(base_temporaire):
    """Le filtrage construit sa clause WHERE, mais passe toujours les valeurs
    en parametres : une injection ne peut pas s'y glisser."""
    bd.creer_action("Internet Fixe", 2026, 6, "Action A",
                    "s.benammar", "responsable_commercial")
    # Si la valeur etait collee dans la requete, ce filtre renverrait tout.
    assert bd.lire_actions(categorie="' OR '1'='1") == []


# ============================================================================
#  Suppression
# ============================================================================
def test_une_action_supprimee_disparait(base_temporaire):
    identifiant = bd.creer_action("Mobile", 2026, 6, "Action a annuler",
                                  "s.benammar", "responsable_commercial")
    assert bd.supprimer_action(identifiant) is True
    assert bd.lire_actions() == []
    assert bd.supprimer_action(identifiant) is False


def test_la_reinitialisation_ne_supprime_pas_les_actions(base_temporaire):
    """Revenir aux donnees de demonstration ne doit pas effacer les decisions.

    Les ventes sont des donnees de demonstration, remplaçables ; les actions
    sont le travail des utilisateurs, et n'ont pas a disparaitre avec elles.
    """
    bd.creer_action("Mobile", 2026, 6, "Une decision a conserver",
                    "s.benammar", "responsable_commercial")
    bd.reinitialiser_depuis_csv()
    assert len(bd.lire_actions()) == 1
