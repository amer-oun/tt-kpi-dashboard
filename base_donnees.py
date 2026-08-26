"""Module de gestion de la BASE DE DONNEES de KPIlot (SQLite).

Pourquoi une base de donnees plutot que de lire directement les CSV ?
---------------------------------------------------------------------
Jusqu'ici l'application lisait ses donnees dans des fichiers CSV. Cela
fonctionne, mais une base de donnees apporte trois choses qu'un fichier
texte ne sait pas faire :

  1. elle stocke les COMPTES UTILISATEURS (avec un mot de passe protege),
     ce qui permet de distinguer le responsable commercial de l'analyste ;
  2. elle permet d'INTERROGER les donnees avec le langage SQL
     (SELECT ... WHERE ...) au lieu de tout charger en memoire ;
  3. elle garantit un format : une colonne declaree INTEGER n'acceptera
     pas du texte par erreur.

Pourquoi SQLite ?
-----------------
SQLite est une base de donnees "sans serveur" : toute la base tient dans
un seul fichier (data/kpilot.db). Elle est INCLUSE dans Python (module
sqlite3), il n'y a donc rien a installer ni a configurer. C'est le bon
choix pour une application de cette taille.

Comment la base est-elle alimentee ?
------------------------------------
Les fichiers CSV restent la SOURCE fournie par le service commercial.
Au premier demarrage, l'application construit la base a partir de ces
fichiers (fonction initialiser_base). Ensuite, chaque import mensuel
ecrit directement dans la base.
"""

import hashlib
import os
import sqlite3

import pandas as pd

# Emplacement du fichier de base de donnees (un seul fichier = toute la base)
CHEMIN_BASE = os.path.join("data", "kpilot.db")

# Fichiers CSV servant a construire la base au premier demarrage
CSV_VENTES = os.path.join("data", "ventes.csv")
CSV_OBJECTIFS = os.path.join("data", "objectifs.csv")

# Comptes crees automatiquement au premier demarrage.
# Format : (nom d'utilisateur, mot de passe, role, nom affiche)
# Les deux roles correspondent aux deux acteurs identifies au chapitre 2.
#
# IMPORTANT - mots de passe et depot public
# -----------------------------------------
# Ce projet est une DEMONSTRATION sur des donnees simulees : les mots de passe
# ci-dessous sont volontairement publics pour que le jury puisse tester
# l'application. Dans un deploiement reel, on ne met JAMAIS un mot de passe
# dans le code source, car celui-ci est lisible par tous sur GitHub.
#
# La bonne pratique, que ce code applique deja, consiste a lire le mot de passe
# dans une VARIABLE D'ENVIRONNEMENT du serveur : la valeur reste alors en
# dehors du code. Si les variables KPILOT_MDP_RESPONSABLE et
# KPILOT_MDP_ANALYSTE sont definies, ce sont elles qui sont utilisees ;
# sinon on retombe sur les mots de passe de demonstration.
COMPTES_PAR_DEFAUT = [
    (
        "s.benammar",
        os.environ.get("KPILOT_MDP_RESPONSABLE", "Salma2026"),
        "responsable_commercial",
        "Salma Ben Ammar",
    ),
    (
        "k.trabelsi",
        os.environ.get("KPILOT_MDP_ANALYSTE", "Karim2026"),
        "analyste_direction",
        "Karim Trabelsi",
    ),
]

# Nombre d'iterations pour le hachage du mot de passe. Plus le nombre est
# grand, plus il est long de tester des mots de passe au hasard.
ITERATIONS_HACHAGE = 100_000


# ============================================================================
#  1. Securite : hachage des mots de passe
# ============================================================================
def hacher_mot_de_passe(mot_de_passe, sel):
    """Transforme un mot de passe en une empreinte illisible (un "hash").

    On ne stocke JAMAIS un mot de passe en clair dans une base de donnees :
    si quelqu'un ouvrait le fichier, il lirait tous les mots de passe.
    On stocke a la place son EMPREINTE, calculee par une fonction a sens
    unique : on peut calculer l'empreinte a partir du mot de passe, mais on
    ne peut pas retrouver le mot de passe a partir de l'empreinte.

    Le "sel" est une valeur aleatoire propre a chaque utilisateur, ajoutee
    avant le calcul. Sans lui, deux personnes ayant le meme mot de passe
    auraient la meme empreinte, ce qui donnerait une information a un
    attaquant.

    On utilise PBKDF2, un algorithme standard fourni par Python.
    """
    empreinte = hashlib.pbkdf2_hmac(
        "sha256",                    # algorithme de hachage
        mot_de_passe.encode("utf-8"),  # le mot de passe, converti en octets
        bytes.fromhex(sel),          # le sel, converti en octets
        ITERATIONS_HACHAGE,
    )
    return empreinte.hex()


def generer_sel():
    """Cree un sel aleatoire de 16 octets, represente en hexadecimal."""
    return os.urandom(16).hex()


# ============================================================================
#  2. Connexion et creation des tables
# ============================================================================
def ouvrir_connexion():
    """Ouvre une connexion vers le fichier de base de donnees.

    check_same_thread=False est necessaire avec Streamlit, qui peut
    executer le script depuis plusieurs fils d'execution differents.
    """
    return sqlite3.connect(CHEMIN_BASE, check_same_thread=False)


def creer_tables(connexion):
    """Cree les trois tables de l'application si elles n'existent pas.

    - utilisateurs : les comptes et leur role ;
    - ventes       : les realisations journalieres (une ligne = un jour,
                     une sous-categorie, une region) ;
    - objectifs    : la cible mensuelle de chaque categorie.

    "IF NOT EXISTS" evite une erreur si la table est deja la.
    """
    connexion.execute(
        """
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_utilisateur   TEXT    NOT NULL UNIQUE,
            mot_de_passe      TEXT    NOT NULL,
            sel               TEXT    NOT NULL,
            role              TEXT    NOT NULL,
            nom_complet       TEXT    NOT NULL
        )
        """
    )
    connexion.execute(
        """
        CREATE TABLE IF NOT EXISTS ventes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT    NOT NULL,
            categorie       TEXT    NOT NULL,
            sous_categorie  TEXT    NOT NULL,
            quantite        INTEGER NOT NULL,
            region          TEXT    NOT NULL
        )
        """
    )
    connexion.execute(
        """
        CREATE TABLE IF NOT EXISTS objectifs (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            categorie         TEXT    NOT NULL,
            annee             INTEGER NOT NULL,
            mois              INTEGER NOT NULL,
            objectif_mensuel  INTEGER NOT NULL
        )
        """
    )
    connexion.commit()


def creer_comptes_par_defaut(connexion):
    """Cree les comptes utilisateurs, ou met a jour ceux qui existent deja.

    Si le compte n'existe pas, on l'insere. S'il existe, on rafraichit son role
    et son nom : ainsi, changer un libelle dans COMPTES_PAR_DEFAUT suffit, sans
    avoir a supprimer la base. Le mot de passe, lui, n'est reecrit que si le
    compte vient d'etre cree (on n'ecrase pas un mot de passe deja en place).
    """
    for nom_utilisateur, mot_de_passe, role, nom_complet in COMPTES_PAR_DEFAUT:
        # A-t-on deja ce compte ? (le "?" est un parametre : voir note plus bas)
        deja_la = connexion.execute(
            "SELECT COUNT(*) FROM utilisateurs WHERE nom_utilisateur = ?",
            (nom_utilisateur,),
        ).fetchone()[0]

        if deja_la == 0:
            sel = generer_sel()
            connexion.execute(
                """INSERT INTO utilisateurs
                   (nom_utilisateur, mot_de_passe, sel, role, nom_complet)
                   VALUES (?, ?, ?, ?, ?)""",
                (nom_utilisateur, hacher_mot_de_passe(mot_de_passe, sel), sel, role, nom_complet),
            )
        else:
            connexion.execute(
                "UPDATE utilisateurs SET role = ?, nom_complet = ? WHERE nom_utilisateur = ?",
                (role, nom_complet, nom_utilisateur),
            )

    # On supprime les comptes qui ne figurent plus dans COMPTES_PAR_DEFAUT.
    # Les comptes de cette application sont declares dans le code : la table
    # doit donc refleter exactement cette liste. Sans ce menage, renommer un
    # identifiant laisserait l'ancien compte actif dans la base, toujours
    # utilisable pour se connecter alors qu'il n'apparait plus nulle part.
    noms_attendus = [compte[0] for compte in COMPTES_PAR_DEFAUT]
    marqueurs = ",".join("?" for _ in noms_attendus)
    connexion.execute(
        f"DELETE FROM utilisateurs WHERE nom_utilisateur NOT IN ({marqueurs})",
        noms_attendus,
    )
    connexion.commit()


def initialiser_base():
    """Prepare la base : cree le fichier, les tables, les comptes et les donnees.

    Cette fonction est appelee au demarrage de l'application. Elle est
    "idempotente" : on peut l'appeler autant de fois qu'on veut, elle ne
    recree pas ce qui existe deja.
    """
    os.makedirs(os.path.dirname(CHEMIN_BASE), exist_ok=True)
    connexion = ouvrir_connexion()
    try:
        creer_tables(connexion)
        creer_comptes_par_defaut(connexion)

        # Si la table ventes est vide, on la remplit depuis les fichiers CSV
        nb_ventes = connexion.execute("SELECT COUNT(*) FROM ventes").fetchone()[0]
        if nb_ventes == 0:
            charger_csv_dans_base(connexion)
    finally:
        connexion.close()


def charger_csv_dans_base(connexion):
    """Copie le contenu des fichiers CSV dans les tables ventes et objectifs.

    pandas sait ecrire directement un tableau dans une base SQL avec
    to_sql(). "if_exists='append'" ajoute les lignes a la table existante
    (sans supprimer la structure creee par CREATE TABLE).
    """
    if os.path.exists(CSV_VENTES):
        ventes = pd.read_csv(CSV_VENTES)
        ventes.to_sql("ventes", connexion, if_exists="append", index=False)

    if os.path.exists(CSV_OBJECTIFS):
        objectifs = pd.read_csv(CSV_OBJECTIFS)
        objectifs.to_sql("objectifs", connexion, if_exists="append", index=False)

    connexion.commit()


# ============================================================================
#  3. Lecture des donnees (requetes SELECT)
# ============================================================================
def lire_ventes():
    """Renvoie toutes les ventes de la base, sous forme de tableau pandas.

    pd.read_sql_query execute une requete SQL et range le resultat dans un
    DataFrame, exactement comme le faisait pd.read_csv auparavant. Le reste
    de l'application (kpi.py) n'a donc pas besoin d'etre modifie.
    """
    connexion = ouvrir_connexion()
    try:
        return pd.read_sql_query(
            "SELECT date, categorie, sous_categorie, quantite, region FROM ventes",
            connexion,
        )
    finally:
        connexion.close()


def lire_objectifs():
    """Renvoie tous les objectifs mensuels de la base."""
    connexion = ouvrir_connexion()
    try:
        return pd.read_sql_query(
            "SELECT categorie, annee, mois, objectif_mensuel FROM objectifs",
            connexion,
        )
    finally:
        connexion.close()


def compter_lignes():
    """Renvoie le nombre de lignes de chaque table (utile pour l'affichage)."""
    connexion = ouvrir_connexion()
    try:
        return {
            "utilisateurs": connexion.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0],
            "ventes": connexion.execute("SELECT COUNT(*) FROM ventes").fetchone()[0],
            "objectifs": connexion.execute("SELECT COUNT(*) FROM objectifs").fetchone()[0],
        }
    finally:
        connexion.close()


# ============================================================================
#  4. Authentification
# ============================================================================
def verifier_identifiants(nom_utilisateur, mot_de_passe):
    """Verifie un couple identifiant / mot de passe.

    Renvoie un dictionnaire decrivant l'utilisateur si tout est correct,
    sinon None.

    Principe : on relit le SEL de cet utilisateur, on recalcule l'empreinte
    du mot de passe saisi avec ce sel, et on compare a l'empreinte stockee.
    Si les deux empreintes sont identiques, le mot de passe est le bon.

    Note sur les "?" dans la requete : ce sont des PARAMETRES. On ne colle
    jamais directement la saisie de l'utilisateur dans une requete SQL,
    sinon quelqu'un pourrait y glisser du code SQL malveillant (c'est ce
    qu'on appelle une INJECTION SQL). Les "?" protegent contre cela.
    """
    connexion = ouvrir_connexion()
    try:
        ligne = connexion.execute(
            """SELECT nom_utilisateur, mot_de_passe, sel, role, nom_complet
               FROM utilisateurs WHERE nom_utilisateur = ?""",
            (nom_utilisateur,),
        ).fetchone()
    finally:
        connexion.close()

    if ligne is None:
        return None  # aucun compte a ce nom

    nom, empreinte_stockee, sel, role, nom_complet = ligne

    # hmac.compare_digest compare deux chaines en un temps constant, ce qui
    # evite de donner un indice a un attaquant selon la vitesse de reponse.
    import hmac
    if not hmac.compare_digest(hacher_mot_de_passe(mot_de_passe, sel), empreinte_stockee):
        return None  # mot de passe incorrect

    return {"nom_utilisateur": nom, "role": role, "nom_complet": nom_complet}


# ============================================================================
#  5. Import mensuel : ecriture des realisations dans la base
# ============================================================================
def importer_ventes(nouvelles_ventes):
    """Ajoute dans la base les realisations d'un fichier importe.

    Regle retenue : le fichier mensuel REMPLACE les donnees des mois qu'il
    contient. Concretement, si l'utilisateur depose le fichier de juillet
    2026, on supprime d'abord les ventes de juillet 2026 deja presentes,
    puis on insere celles du fichier. Ainsi, reimporter deux fois le meme
    fichier ne cree pas de doublons, et corriger un fichier errone consiste
    simplement a le redeposer.

    Renvoie un dictionnaire resumant l'operation (mois traites, lignes
    supprimees, lignes ajoutees).
    """
    donnees = nouvelles_ventes.copy()

    # On extrait l'annee et le mois de chaque ligne pour savoir quels mois
    # sont concernes par ce fichier.
    dates = pd.to_datetime(donnees["date"])
    donnees["date"] = dates.dt.strftime("%Y-%m-%d")
    mois_concernes = sorted({(int(d.year), int(d.month)) for d in dates})

    connexion = ouvrir_connexion()
    try:
        lignes_supprimees = 0
        for annee, mois in mois_concernes:
            # strftime('%Y', date) extrait l'annee de la colonne date en SQL.
            curseur = connexion.execute(
                """DELETE FROM ventes
                   WHERE CAST(strftime('%Y', date) AS INTEGER) = ?
                     AND CAST(strftime('%m', date) AS INTEGER) = ?""",
                (annee, mois),
            )
            lignes_supprimees += curseur.rowcount

        colonnes = ["date", "categorie", "sous_categorie", "quantite", "region"]
        donnees[colonnes].to_sql("ventes", connexion, if_exists="append", index=False)
        connexion.commit()
    finally:
        connexion.close()

    return {
        "mois": mois_concernes,
        "supprimees": lignes_supprimees,
        "ajoutees": len(donnees),
    }


def reinitialiser_depuis_csv():
    """Remet la base dans son etat de demonstration.

    On vide les tables de donnees (pas les comptes utilisateurs !) puis on
    les recharge depuis les fichiers CSV d'origine. Cela sert au bouton
    "Revenir aux donnees de demonstration" du tableau de bord.
    """
    connexion = ouvrir_connexion()
    try:
        connexion.execute("DELETE FROM ventes")
        connexion.execute("DELETE FROM objectifs")
        connexion.commit()
        charger_csv_dans_base(connexion)
    finally:
        connexion.close()


# ============================================================================
#  6. Gestion du compte : changer son mot de passe
# ============================================================================
LONGUEUR_MINIMALE_MOT_DE_PASSE = 8


def changer_mot_de_passe(nom_utilisateur, ancien, nouveau):
    """Change le mot de passe d'un utilisateur.

    Renvoie (True, message) si le changement a eu lieu, (False, message) sinon.

    Trois verifications, dans cet ordre :
      1. l'ancien mot de passe doit etre correct (on reutilise pour cela la
         fonction d'authentification : on ne reecrit pas la meme logique deux
         fois, et on ne peut donc pas se tromper d'un cote seulement) ;
      2. le nouveau doit faire au moins 8 caracteres ;
      3. le nouveau doit etre different de l'ancien.

    Point important : on genere un NOUVEAU SEL a chaque changement. Ainsi,
    meme si quelqu'un avait vu l'ancienne empreinte, elle devient inutile.
    """
    if verifier_identifiants(nom_utilisateur, ancien) is None:
        return False, "Mot de passe actuel incorrect."
    if len(nouveau) < LONGUEUR_MINIMALE_MOT_DE_PASSE:
        return False, (
            f"Le nouveau mot de passe doit faire au moins "
            f"{LONGUEUR_MINIMALE_MOT_DE_PASSE} caracteres."
        )
    if nouveau == ancien:
        return False, "Le nouveau mot de passe doit etre different de l'ancien."

    sel = generer_sel()
    empreinte = hacher_mot_de_passe(nouveau, sel)

    connexion = ouvrir_connexion()
    try:
        connexion.execute(
            "UPDATE utilisateurs SET mot_de_passe = ?, sel = ? WHERE nom_utilisateur = ?",
            (empreinte, sel, nom_utilisateur),
        )
        connexion.commit()
    finally:
        connexion.close()
    return True, "Mot de passe modifie."


def lire_utilisateur(nom_utilisateur):
    """Renvoie la fiche d'un utilisateur (sans son mot de passe), ou None.

    Sert a afficher la page "Mon compte" : on veut le nom et le role, jamais
    l'empreinte ni le sel, qui n'ont aucune raison de circuler dans l'interface.
    """
    connexion = ouvrir_connexion()
    try:
        ligne = connexion.execute(
            "SELECT nom_utilisateur, role, nom_complet FROM utilisateurs "
            "WHERE nom_utilisateur = ?",
            (nom_utilisateur,),
        ).fetchone()
    finally:
        connexion.close()
    if ligne is None:
        return None
    return {"nom_utilisateur": ligne[0], "role": ligne[1], "nom_complet": ligne[2]}


# ============================================================================
#  Execution directe : permet de (re)construire la base depuis le terminal
#  avec la commande :  python base_donnees.py
# ============================================================================
if __name__ == "__main__":
    initialiser_base()
    totaux = compter_lignes()
    print("=== Base de donnees KPIlot initialisee ===")
    print(f"Fichier : {CHEMIN_BASE}")
    print(f"  utilisateurs : {totaux['utilisateurs']}")
    print(f"  ventes       : {totaux['ventes']}")
    print(f"  objectifs    : {totaux['objectifs']}")
    print()
    print("Comptes disponibles :")
    for nom_utilisateur, mot_de_passe, role, _ in COMPTES_PAR_DEFAUT:
        print(f"  {nom_utilisateur:12s} / {mot_de_passe:18s} ({role})")
