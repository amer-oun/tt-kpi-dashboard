"""Tests unitaires du module base_donnees.py.

Ces tests verifient les deux aspects sensibles de la base de donnees :
la SECURITE des mots de passe et la FIABILITE de l'import mensuel.

Chaque test travaille sur une base TEMPORAIRE, creee dans un dossier jetable
fourni par pytest (tmp_path). La vraie base data/kpilot.db n'est donc jamais
touchee : on peut lancer les tests autant de fois qu'on veut sans risque.

Lancer les tests :  pytest -v
"""

import pandas as pd
import pytest

import base_donnees as bd


@pytest.fixture
def base_temporaire(tmp_path, monkeypatch):
    """Prepare une base de donnees vide et jetable pour un test.

    Une "fixture" pytest est un decor de test : le code place avant le mot-cle
    'yield' s'execute AVANT le test, et prepare ce dont il a besoin.

    monkeypatch remplace temporairement la valeur d'une variable du module.
    Ici, on fait pointer bd.CHEMIN_BASE vers un fichier du dossier temporaire,
    et les chemins CSV vers de petits fichiers d'exemple que l'on cree nous-memes.
    """
    # Un mini jeu de ventes : 2 jours de janvier 2026
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
    yield  # c'est ici que le test s'execute


# ============================================================================
#  Securite des mots de passe
# ============================================================================
def test_le_mot_de_passe_n_est_jamais_stocke_en_clair(base_temporaire):
    """La base ne doit contenir aucun mot de passe lisible."""
    # Arrange / Act : on lit directement le contenu de la table utilisateurs
    connexion = bd.ouvrir_connexion()
    lignes = connexion.execute("SELECT mot_de_passe FROM utilisateurs").fetchall()
    connexion.close()

    # Assert : aucune empreinte stockee ne ressemble au mot de passe d'origine
    empreintes = [ligne[0] for ligne in lignes]
    for _, mot_de_passe_clair, _, _ in bd.COMPTES_PAR_DEFAUT:
        assert mot_de_passe_clair not in empreintes


def test_deux_sels_differents_donnent_deux_empreintes_differentes():
    """Le sel garantit que deux mots de passe identiques ne se ressemblent pas."""
    # Arrange : le MEME mot de passe, deux sels differents
    sel_a, sel_b = bd.generer_sel(), bd.generer_sel()
    # Act
    empreinte_a = bd.hacher_mot_de_passe("motdepasse", sel_a)
    empreinte_b = bd.hacher_mot_de_passe("motdepasse", sel_b)
    # Assert
    assert empreinte_a != empreinte_b


def test_le_hachage_est_reproductible():
    """Avec le meme sel, le meme mot de passe donne toujours la meme empreinte.

    C'est cette propriete qui permet de verifier un mot de passe sans jamais
    l'avoir stocke.
    """
    sel = bd.generer_sel()
    assert bd.hacher_mot_de_passe("secret", sel) == bd.hacher_mot_de_passe("secret", sel)


# ============================================================================
#  Authentification et roles
# ============================================================================
def test_connexion_avec_les_bons_identifiants(base_temporaire):
    """Un identifiant et un mot de passe corrects renvoient le bon role."""
    # Act
    responsable = bd.verifier_identifiants("s.benammar", "Salma2026")
    analyste = bd.verifier_identifiants("k.trabelsi", "Karim2026")
    # Assert
    assert responsable["role"] == "responsable_commercial"
    assert analyste["role"] == "analyste_direction"


def test_connexion_refusee_si_mot_de_passe_faux(base_temporaire):
    """Un mauvais mot de passe ne doit jamais laisser entrer."""
    assert bd.verifier_identifiants("s.benammar", "mauvais") is None


def test_connexion_refusee_si_compte_inconnu(base_temporaire):
    """Un compte qui n'existe pas ne doit jamais laisser entrer."""
    assert bd.verifier_identifiants("inconnu", "Salma2026") is None


def test_resistance_a_l_injection_sql(base_temporaire):
    """Une tentative d'injection SQL ne doit pas contourner la connexion.

    La chaine "' OR '1'='1" est l'attaque classique : si la requete etait
    construite en collant le texte saisi, elle deviendrait toujours vraie et
    ouvrirait la session. Les parametres '?' l'en empechent.
    """
    assert bd.verifier_identifiants("' OR '1'='1", "peu importe") is None


# ============================================================================
#  Import mensuel
# ============================================================================
def test_import_ajoute_les_lignes_en_base(base_temporaire):
    """Importer un fichier augmente le nombre de ventes enregistrees."""
    # Arrange
    avant = bd.compter_lignes()["ventes"]
    fevrier = pd.DataFrame(
        {
            "date": ["2026-02-01", "2026-02-02"],
            "categorie": ["Internet Fixe", "Mobile"],
            "sous_categorie": ["FO", "Prepaye"],
            "quantite": [5, 7],
            "region": ["Sousse", "Nabeul"],
        }
    )
    # Act
    bd.importer_ventes(fevrier)
    # Assert
    assert bd.compter_lignes()["ventes"] == avant + 2


def test_reimporter_le_meme_fichier_ne_cree_pas_de_doublon(base_temporaire):
    """Deposer deux fois le meme fichier doit laisser la base inchangee.

    C'est la regle de remplacement par mois : les lignes du mois concerne
    sont d'abord supprimees, puis reinserees.
    """
    # Arrange
    mars = pd.DataFrame(
        {
            "date": ["2026-03-01"],
            "categorie": ["Mobile"],
            "sous_categorie": ["Data"],
            "quantite": [42],
            "region": ["Gabes"],
        }
    )
    bd.importer_ventes(mars)
    apres_premier_import = bd.compter_lignes()["ventes"]
    # Act : on reimporte exactement le meme fichier
    resume = bd.importer_ventes(mars)
    # Assert
    assert bd.compter_lignes()["ventes"] == apres_premier_import
    assert resume["supprimees"] == 1  # l'ancienne ligne a bien ete remplacee


def test_import_ne_touche_pas_aux_autres_mois(base_temporaire):
    """Importer avril ne doit pas effacer les ventes de janvier."""
    # Arrange : janvier contient deja 2 lignes (voir la fixture)
    avril = pd.DataFrame(
        {
            "date": ["2026-04-01"],
            "categorie": ["Mobile"],
            "sous_categorie": ["Postpaye"],
            "quantite": [9],
            "region": ["Kairouan"],
        }
    )
    # Act
    bd.importer_ventes(avril)
    # Assert : les ventes de janvier sont toujours la
    ventes = bd.lire_ventes()
    janvier = ventes[ventes["date"].str.startswith("2026-01")]
    assert len(janvier) == 2


def test_reinitialisation_restaure_les_donnees_de_demonstration(base_temporaire):
    """Le bouton de reinitialisation doit revenir a l'etat de depart."""
    # Arrange : on pollue la base avec un import
    mai = pd.DataFrame(
        {
            "date": ["2026-05-01"],
            "categorie": ["Mobile"],
            "sous_categorie": ["Data"],
            "quantite": [1],
            "region": ["Bizerte"],
        }
    )
    bd.importer_ventes(mai)
    # Act
    bd.reinitialiser_depuis_csv()
    # Assert : on retrouve les 2 lignes du CSV d'origine, et les comptes restent
    totaux = bd.compter_lignes()
    assert totaux["ventes"] == 2
    assert totaux["utilisateurs"] == 2


def test_la_base_ne_garde_que_les_comptes_declares(base_temporaire):
    """Un compte retire du code doit disparaitre de la base.

    Sans ce menage, renommer un identifiant laisserait l'ancien compte actif :
    il n'apparaitrait plus a l'ecran mais permettrait encore de se connecter.
    """
    # Arrange : on ajoute a la main un compte qui n'est pas declare dans le code
    connexion = bd.ouvrir_connexion()
    sel = bd.generer_sel()
    connexion.execute(
        """INSERT INTO utilisateurs
           (nom_utilisateur, mot_de_passe, sel, role, nom_complet)
           VALUES (?, ?, ?, ?, ?)""",
        ("ancien.compte", bd.hacher_mot_de_passe("motdepasse", sel), sel,
         "responsable_commercial", "Compte oublie"),
    )
    connexion.commit()
    connexion.close()
    assert bd.verifier_identifiants("ancien.compte", "motdepasse") is not None

    # Act : on relance l'initialisation
    bd.initialiser_base()

    # Assert : le compte non declare a ete supprime, les autres sont intacts
    assert bd.verifier_identifiants("ancien.compte", "motdepasse") is None
    assert bd.compter_lignes()["utilisateurs"] == len(bd.COMPTES_PAR_DEFAUT)
