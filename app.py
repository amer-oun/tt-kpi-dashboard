import base64
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Logique de calcul KPI partagee avec calcul_kpi.py (voir kpi.py)
from kpi import preparer_ventes, calculer_kpi

# Base de donnees SQLite : comptes utilisateurs, ventes et objectifs
# (voir base_donnees.py pour le detail des tables et de la securite)
import base_donnees as bd

# ============================================================================
#  Palette "console de supervision telecom" (reutilisee CSS + graphiques)
# ============================================================================
NUIT = "#0A2A4A"     # bleu nuit (en-tetes, chiffres)
BLEU = "#0072BC"     # bleu Tunisie Telecom (accent principal)
AMBRE = "#D97706"    # accent (bouton d'action) - recommande par la skill UI/UX
ROUGE = "#D62828"    # rouge (rappel drapeau) : alertes / objectif manque de loin
VERT = "#1B9C6B"     # objectif atteint
ORANGE = "#E8833A"   # proche de l'objectif
GRIS = "#B9C4CF"     # neutre (barres objectif)

# Variantes assombries des couleurs d'etat, reservees au PETIT TEXTE.
# L'ambre, l'orange et le vert ci-dessus sont lumineux : ils conviennent a un
# aplat ou a un gros chiffre, mais tombent sous le seuil de lisibilite
# (4,5:1 sur fond blanc) des qu'ils servent a ecrire une etiquette.
AMBRE_TEXTE = "#B45309"
ORANGE_TEXTE = "#B45309"
VERT_TEXTE = "#157F57"


def charger_si_existe(chemin):
    """Charge un CSV s'il existe, sinon renvoie None.
    Pour les fichiers produits aux etapes 6 et 7 : si les scripts n'ont pas
    ete lances, on affiche un message plutot qu'une erreur."""
    if os.path.exists(chemin):
        return pd.read_csv(chemin)
    return None


# Colonnes que DOIT contenir un fichier de realisations importe (meme format
# que data/ventes.csv). On s'en sert pour valider ce que l'utilisateur depose.
COLONNES_ATTENDUES = ["date", "categorie", "sous_categorie", "quantite", "region"]


def lire_fichier_importe(fichier):
    """Lit le fichier depose par l'utilisateur (Excel .xlsx ou CSV) et renvoie
    un DataFrame pandas. On choisit le bon lecteur selon l'extension du nom."""
    nom = fichier.name.lower()
    if nom.endswith(".csv"):
        return pd.read_csv(fichier)
    # .xlsx / .xls : necessite la librairie openpyxl (deja installee)
    return pd.read_excel(fichier)


def valider_ventes(df):
    """Verifie qu'un fichier importe est utilisable.

    Renvoie (True, message) si tout va bien, sinon (False, message d'erreur).
    On controle la presence des colonnes obligatoires et le fait que la
    colonne 'quantite' contienne bien des nombres.
    """
    colonnes_manquantes = [c for c in COLONNES_ATTENDUES if c not in df.columns]
    if colonnes_manquantes:
        return False, "Colonnes manquantes : " + ", ".join(colonnes_manquantes)
    # 'quantite' doit etre convertible en nombre
    try:
        pd.to_numeric(df["quantite"])
    except (ValueError, TypeError):
        return False, "La colonne 'quantite' doit contenir uniquement des nombres."
    if len(df) == 0:
        return False, "Le fichier est vide (aucune ligne de vente)."
    return True, f"Fichier valide : {len(df)} lignes de ventes lues."


def logo_html():
    """Renvoie le logo a afficher dans l'en-tete.
    Si un fichier image existe dans assets/, on l'integre directement dans la
    page (encode en base64 -> aucune dependance externe). Sinon, on retombe
    sur une pastille "TT" pour ne pas casser l'affichage."""
    chemins_possibles = [
        "assets/logo_tt.png",
        "assets/logo_tt.svg",
        "assets/logo_tt.jpg",
        "assets/logo.png",
    ]
    for chemin in chemins_possibles:
        if os.path.exists(chemin):
            extension = chemin.rsplit(".", 1)[-1].lower()
            type_mime = {
                "png": "image/png",
                "svg": "image/svg+xml",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
            }.get(extension, "image/png")
            with open(chemin, "rb") as fichier:
                encode = base64.b64encode(fichier.read()).decode()
            return f'<img class="tt-logo-img" src="data:{type_mime};base64,{encode}" alt="Tunisie Telecom"/>'
    # Repli : pastille "TT" tant que le logo officiel n'est pas depose
    return '<div class="tt-mark">TT</div>'


def image_data_uri(chemin):
    """Encode une image locale en URL 'data:' (base64) -> integrable dans le HTML
    sans dependance externe. Sert notamment au logo KPIlot dans l'en-tete."""
    extension = chemin.rsplit(".", 1)[-1].lower()
    type_mime = {
        "png": "image/png", "svg": "image/svg+xml",
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
    }.get(extension, "image/png")
    with open(chemin, "rb") as fichier:
        encode = base64.b64encode(fichier.read()).decode()
    return f"data:{type_mime};base64,{encode}"


def couleur_selon_taux(taux):
    """Vert si objectif atteint, orange si on s'en approche, rouge sinon."""
    if taux is None:
        return BLEU
    if taux >= 100:
        return VERT
    if taux >= 90:
        return ORANGE
    return ROUGE


def jauge_taux(valeur, titre):
    """Cree une jauge (facon compteur de vitesse) pour un taux de realisation.
    go.Indicator est le type de graphique Plotly dedie aux jauges/compteurs.
    - l'aiguille (bar) pointe la valeur ;
    - les 'steps' colorent le fond (rouge/orange/vert) ;
    - le 'threshold' trace une ligne noire sur 100 % = l'objectif a atteindre.
    """
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=valeur,
            number={"suffix": " %"},
            title={"text": titre, "font": {"size": 15}},
            gauge={
                "axis": {"range": [0, 120]},
                "bar": {"color": couleur_selon_taux(valeur)},
                "steps": [
                    {"range": [0, 90], "color": "#F3D6D6"},    # zone rouge pale
                    {"range": [90, 100], "color": "#FBE7D3"},  # zone orange pale
                    {"range": [100, 120], "color": "#D7F0E2"}, # zone verte pale
                ],
                "threshold": {"line": {"color": NUIT, "width": 3}, "thickness": 0.85, "value": 100},
            },
        )
    )
    figure.update_layout(height=240, margin=dict(t=45, b=10, l=25, r=25))
    return figure


def texte_alerte(categorie, taux, manque):
    """Retourne la phrase d'alerte pour une categorie (reutilisee ecran + PDF)."""
    if taux is None:
        return f"{categorie} : pas d'objectif defini."
    if taux >= 100:
        return f"{categorie} : objectif atteint ({taux} %)."
    if taux >= 90:
        return f"{categorie} : proche de l'objectif ({taux} %), il manque {manque} ventes."
    return f"{categorie} : en retard ({taux} %), il manque {manque} ventes."


def generer_rapport_pdf(categorie, annee, total_realise, total_objectif, taux_global, ecart_global, alertes):
    """Construit un rapport PDF d'une page et le renvoie en octets (bytes).
    On importe fpdf ICI (import 'paresseux') pour que le dashboard fonctionne
    meme si la librairie n'est pas installee (le bouton afficherait une erreur).
    Note : on ecrit sans accents, car la police de base du PDF gere mal l'UTF-8."""
    from fpdf import FPDF, XPos, YPos
    from datetime import date

    pdf = FPDF()
    pdf.add_page()

    # En-tete
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(10, 42, 74)
    pdf.cell(0, 10, "Rapport KPI - Tunisie Telecom", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(90, 112, 134)
    pdf.cell(0, 8, f"Categorie : {categorie}   |   Annee : {annee}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, f"Genere le : {date.today().strftime('%d/%m/%Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Chiffres cles
    pdf.set_text_color(30, 41, 59)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Chiffres cles", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    taux_txt = f"{taux_global} %" if taux_global is not None else "N/A"
    for ligne_pdf in [
        f"- Ventes realisees (cumul) : {total_realise}",
        f"- Objectif (cumul) : {total_objectif}",
        f"- Taux de realisation : {taux_txt}",
        f"- Ecart : {ecart_global:+} ventes",
    ]:
        pdf.cell(0, 7, ligne_pdf, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Alertes par categorie
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, f"Alertes - situation cumulee {annee}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    for _, a in alertes.iterrows():
        manque = int(a["objectif_mensuel"] - a["ventes_reelles"])
        pdf.cell(0, 7, "- " + texte_alerte(a["categorie"], a["taux"], manque),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


def barres_signal(taux, couleur):
    """SIGNATURE du design : un indicateur facon "reception mobile".
    5 barres de hauteur croissante ; on en allume d'autant plus que le taux
    de realisation est eleve (0-20-40-60-80-100 %)."""
    if taux is None:
        taux = 0
    allumees = max(0, min(5, round(taux / 20)))
    barres = ""
    for i in range(1, 6):
        hauteur = 8 + i * 5  # barres de plus en plus hautes
        teinte = couleur if i <= allumees else "#D3DCE6"
        barres += f'<span class="sig-bar" style="height:{hauteur}px;background:{teinte};"></span>'
    return f'<div class="sig-wrap">{barres}</div>'


# Petites icones SVG (style Lucide, trait 2px) : la skill UI/UX interdit les
# emoji comme icones. On les integre en HTML dans les cartes.
ICONES = {
    "ventes": '<path d="M22 7 13.5 15.5 8.5 10.5 2 17"/><path d="M16 7h6v6"/>',
    "objectif": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4"/>',
    "taux": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "annuel": '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
}


def icone_svg(nom, couleur):
    """Renvoie une petite icone SVG coloree (ou rien si le nom est inconnu)."""
    trace = ICONES.get(nom)
    if not trace:
        return ""
    return (
        f'<svg class="tt-card-icone" width="20" height="20" viewBox="0 0 24 24" '
        f'fill="none" stroke="{couleur}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{trace}</svg>'
    )


def carte_kpi(titre, valeur, sous_texte="", couleur=BLEU, extra_html="", icone=""):
    """Fabrique une carte KPI HTML (chiffre en Fira Code facon telemetrie).

    - icone : nom d'une icone SVG (voir ICONES) affichee en haut a droite ;
    """
    return f"""
    <div class="tt-card" style="border-top: 3px solid {couleur};">
        <div class="tt-card-entete">
            <div class="tt-card-titre">{titre}</div>
            {icone_svg(icone, couleur)}
        </div>
        <div class="tt-card-valeur">{valeur}</div>
        <div class="tt-card-sous" style="color:{couleur};">{sous_texte}</div>
        {extra_html}
    </div>
    """


# ============================================================================
#  Configuration de la page (DOIT etre la 1re commande Streamlit)
# ============================================================================
# Favicon de l'onglet : l'icone KPIlot si elle existe, sinon un emoji de repli.
try:
    from PIL import Image
    _favicon = Image.open("assets/logo_kpilot_icon.png")
except Exception:
    _favicon = "📈"

st.set_page_config(
    page_title="KPIlot - Performance commerciale TT",
    page_icon=_favicon,
    layout="wide",
    # "auto" : barre laterale ouverte sur PC, repliee automatiquement sur telephone
    # (sinon elle s'ouvre par-dessus le contenu au chargement mobile).
    initial_sidebar_state="auto",
)

# ============================================================================
#  CSS : c'est ce qui donne l'identite "console telecom" a Streamlit
# ============================================================================
st.markdown(
    f"""
    <style>
    /* Typographie "data/analytics" recommandee par la skill UI/UX :
       Fira Sans (texte) + Fira Code (chiffres). Repli sur les polices systeme
       si la connexion echoue -> le dashboard reste lisible hors-ligne. */
    @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;600;700&family=Fira+Sans:wght@400;500;600;700&display=swap');

    :root {{
        --tt-nuit:{NUIT}; --tt-bleu:{BLEU}; --tt-ambre:{AMBRE};
        --tt-fond:#F8FAFC; --tt-surface:#FFFFFF; --tt-bordure:#DCE6F1;
        --tt-texte:#1E293B; --tt-muet:#5B7086;
        --sans:"Fira Sans","Segoe UI",-apple-system,Roboto,Helvetica,Arial,sans-serif;
        --mono:"Fira Code",Consolas,"SF Mono","Roboto Mono",monospace;
    }}
    html, body, [class*="css"] {{ font-family: var(--sans); }}
    /* densite "dashboard" : marges resserrees */
    .block-container {{ padding-top: 1.2rem; padding-bottom: 2.5rem; max-width: 1280px; }}

    /* ---------- Page de connexion ---------- */
    /* L'en-tete reste sobre : sur un ecran de connexion, l'utilisateur vient
       entrer, pas admirer une banniere. Le titre est centre, mais les textes
       de lecture sont alignes a gauche (un paragraphe centre se lit mal). */
    .kp-login-entete {{ text-align: center; margin: 2.2rem 0 1.6rem 0; }}
    .kp-login-logo {{ height: 42px; }}
    .kp-login-mot {{
        font-size: 1.5rem; font-weight: 700; color: var(--tt-bleu); letter-spacing: -0.02em;
    }}
    .kp-login-titre {{
        color: var(--tt-nuit); margin: 12px 0 3px 0;
        font-size: 1.4rem; font-weight: 700; letter-spacing: -0.015em;
        text-wrap: balance;
    }}
    .kp-login-sous {{
        color: var(--tt-muet); margin: 0 auto; font-size: .88rem; max-width: 60ch;
    }}
    .kp-login-consigne {{
        color: var(--tt-muet); font-size: .88rem;
        margin: 0 0 10px 2px; text-align: left;
    }}

    /* Fiche d'un profil : le cadre est fourni par st.container(border=True),
       on ne redessine donc pas de bordure ici (deux cadres imbriques seraient
       toujours une erreur). */
    .kp-profil-tete {{ display: flex; align-items: center; gap: 12px; }}
    .kp-profil-pastille {{
        width: 42px; height: 42px; border-radius: 50%; flex-shrink: 0;
        display: inline-flex; align-items: center; justify-content: center;
        color: #fff; font-weight: 700; font-size: .95rem; letter-spacing: .5px;
    }}
    .kp-profil-identite {{ display: flex; flex-direction: column; line-height: 1.25; }}
    .kp-profil-nom {{ color: var(--tt-nuit); font-weight: 700; font-size: 1.02rem; }}
    .kp-profil-fonction {{
        font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .7px;
    }}
    .kp-profil-mission {{
        color: var(--tt-texte); font-size: .88rem; line-height: 1.5;
        margin: 12px 0 0 0;
    }}
    .kp-profil-acces {{ color: var(--tt-muet); font-size: .8rem; margin: 7px 0 0 0; }}
    .kp-profil-ids {{
        font-family: var(--mono); font-size: .82rem; color: var(--tt-nuit);
        background: #EEF3F9; border-radius: 8px; padding: 7px 10px;
        margin: 11px 0 12px 0;
    }}
    .kp-profil-sep {{ color: var(--tt-muet); margin: 0 8px; }}

    /* Bouton principal : plein, aux couleurs de l'operateur. Sans cela les
       deux boutons de demonstration ressemblent a des liens desactives. */
    .stButton button[kind="primary"] {{
        background: var(--tt-bleu) !important; color: #fff !important;
        border: 1px solid var(--tt-bleu) !important; border-radius: 9px !important;
        font-weight: 600 !important;
        transition: filter .18s ease !important;
    }}
    .stButton button[kind="primary"]:hover {{ filter: brightness(1.08); }}

    /* Identite dans la barre laterale */
    .kp-qui {{ padding: 2px 0 6px 0; }}
    .kp-qui-nom {{ color: var(--tt-nuit); font-weight: 700; font-size: .98rem; }}
    .kp-qui-role {{
        color: var(--tt-bleu); font-size: .74rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: .8px; margin-top: 2px;
    }}

    .kp-login-pied {{
        color: var(--tt-muet); font-size: .78rem; line-height: 1.55;
        max-width: 78ch; margin: 18px 0 0 2px; text-align: left;
    }}

    /* ---------- Bandeau d'en-tete (masthead) ---------- */
    .tt-masthead {{
        position: relative; overflow: hidden;
        background:
            radial-gradient(circle at 92% -30%, rgba(0,114,188,.45), transparent 45%),
            linear-gradient(120deg, var(--tt-nuit) 0%, #0E3A63 100%);
        border-radius: 16px; padding: 24px 30px 28px 30px; margin-bottom: 22px;
        box-shadow: 0 8px 24px rgba(10,42,74,.20);
        animation: apparition .6s cubic-bezier(.22,1,.36,1) both;
    }}
    /* liseré bleu -> rouge en bas : clin d'oeil au drapeau tunisien */
    .tt-masthead::after {{
        content: ""; position: absolute; left: 0; bottom: 0; height: 4px; width: 100%;
        background: linear-gradient(90deg, var(--tt-bleu) 0%, var(--tt-bleu) 62%, {ROUGE} 62%, {ROUGE} 100%);
    }}
    .tt-brand {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
    .tt-mark {{
        width: 42px; height: 42px; border-radius: 10px; background: #fff; color: var(--tt-nuit);
        font-weight: 800; font-size: 17px; letter-spacing: 1px;
        display: flex; align-items: center; justify-content: center;
    }}
    .tt-masthead .tt-op {{ color: #cfe4f7 !important; font-size: 13px; font-weight: 600;
             text-transform: uppercase; letter-spacing: 2.5px; }}
    .tt-masthead .tt-title {{ color: #ffffff !important; margin: 0;
             font-size: clamp(22px, 5.5vw, 30px);
             font-weight: 700; letter-spacing: -0.5px; }}
    .tt-masthead .tt-sub   {{ color: #9fc4e6 !important; margin: 6px 0 0 0; font-size: 14px;
             letter-spacing: .3px; }}
    .tt-logo-img {{ height: 48px; width: auto; background: #fff; padding: 7px 10px;
             border-radius: 10px; display: block; box-shadow: 0 2px 8px rgba(0,0,0,.12); }}
    /* Logo KPIlot (version blanche) pose directement sur le bandeau fonce */
    .kpilot-logo {{ height: 52px; width: auto; display: block; }}
    .tt-brand .tt-op-sep {{ width: 1px; height: 34px; background: rgba(255,255,255,.22); }}

    /* ---------- Ecran d'accueil propre a chaque role ---------- */
    .kp-ecran {{ margin: 2px 0 14px 0; }}
    .kp-ecran-titre {{
        color: var(--tt-nuit); font-size: 1.45rem; font-weight: 700;
        margin: 0; letter-spacing: -0.01em;
    }}
    .kp-ecran-sous {{
        color: var(--tt-muet); font-size: .93rem; margin: 4px 0 0 0;
        max-width: 68ch;
    }}

    /* Bandeau de tete : l'unique information a retenir en ouvrant l'ecran.
       Bordure pleine (pas de bande laterale coloree) + fond tres legerement
       teinte, pour que le message se distingue sans crier. */
    .kp-bandeau {{
        background: var(--tt-surface); border: 1px solid var(--tt-bordure);
        border-top-width: 3px; border-radius: 12px;
        padding: 14px 18px 15px 18px; margin-bottom: 16px;
    }}
    .kp-bandeau-etiquette {{
        font-size: 11.5px; font-weight: 700; text-transform: uppercase;
        letter-spacing: .9px; margin-bottom: 5px;
    }}
    .kp-bandeau-phrase {{
        color: var(--tt-texte); font-size: 1.05rem; line-height: 1.45;
        max-width: 72ch;
    }}
    .kp-bandeau-detail {{
        color: var(--tt-muet); font-size: .88rem; margin-top: 5px;
    }}

    /* ---------- Cartes KPI (style data-dense + survol) ---------- */
    /* Pas d'animation d'entree : un outil de travail s'ouvre sur la tache,
       il ne fait pas defiler ses cartes a chaque rechargement. Les seules
       transitions conservees traduisent un ETAT (le survol). */
    .tt-card {{
        background: var(--tt-surface); border: 1px solid var(--tt-bordure); border-radius: 14px;
        padding: 15px 18px 16px 18px; box-shadow: 0 1px 3px rgba(10,42,74,.06);
        transition: transform .18s cubic-bezier(.22,1,.36,1),
                    box-shadow .18s cubic-bezier(.22,1,.36,1),
                    border-color .18s ease;
    }}
    .tt-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 15px rgba(10,42,74,.10);
        border-color: #C3D4E8;
    }}
    .tt-card-entete {{ display: flex; align-items: center; justify-content: space-between; }}
    .tt-card-icone {{ opacity: .85; flex-shrink: 0; }}
    .tt-card-titre {{ color: var(--tt-muet); font-size: 12px; font-weight: 600;
                     text-transform: uppercase; letter-spacing: .8px; }}
    .tt-card-valeur {{
        color: var(--tt-nuit); font-family: var(--mono);
        font-size: clamp(26px, 6vw, 31px); font-weight: 600; font-variant-numeric: tabular-nums;
        margin-top: 6px; line-height: 1.1;
    }}
    .tt-card-sous {{ font-size: 13px; font-weight: 600; margin-top: 4px; }}

    /* ---------- Barres de signal (signature) ---------- */
    .sig-wrap {{ display: flex; align-items: flex-end; gap: 4px; height: 34px; margin-top: 10px; }}
    .sig-bar  {{ width: 9px; border-radius: 2px; transition: height .3s ease; }}

    /* ---------- Bouton d'action : accent ambre (skill UI/UX) ---------- */
    .stDownloadButton button {{
        background: var(--tt-ambre) !important; color: #fff !important; border: none !important;
        border-radius: 9px !important; font-weight: 600 !important; padding: 8px 18px !important;
        transition: filter .2s ease, transform .2s ease !important;
    }}
    .stDownloadButton button:hover {{ filter: brightness(1.08); transform: translateY(-1px); }}

    /* ---------- Onglets facon segmented control ---------- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px; background: #E6EDF5; padding: 5px; border-radius: 12px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 9px; padding: 8px 16px; font-weight: 600; font-size: 14px; color: #3A5068;
        transition: background .2s ease, color .2s ease;
    }}
    .stTabs [data-baseweb="tab"]:hover {{ background: #d5e2f0; }}
    .stTabs [aria-selected="true"] {{ background: var(--tt-nuit) !important; color: #fff !important; }}
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

    /* Chiffres du tableau alignes (chiffres tabulaires) */
    [data-testid="stDataFrame"] {{ font-variant-numeric: tabular-nums; }}

    h2, h3 {{ color: var(--tt-nuit); letter-spacing: -0.3px; }}

    /* Focus clavier visible (accessibilite - checklist de la skill) */
    a:focus-visible, button:focus-visible, [data-baseweb="tab"]:focus-visible {{
        outline: 3px solid rgba(0,114,188,.55); outline-offset: 2px; border-radius: 8px;
    }}

    @keyframes apparition {{ from {{ opacity: 0; transform: translateY(8px); }}
                            to {{ opacity: 1; transform: translateY(0); }} }}
    /* Respect de prefers-reduced-motion (accessibilite) */
    @media (prefers-reduced-motion: reduce) {{
        .tt-card, .tt-masthead {{ animation: none; }}
        .tt-card, .sig-bar, .stTabs [data-baseweb="tab"], .stDownloadButton button {{ transition: none; }}
        .tt-card:hover {{ transform: none; }}
    }}

    /* ================= ADAPTATION MOBILE / TABLETTE (responsive) =================
       Sur petit ecran (<= 640px), on resserre les marges, on reduit le bandeau
       et on rend les onglets plus compacts. Les cartes KPI (st.columns) s'empilent
       deja toutes seules en vertical grace a Streamlit. */
    @media (max-width: 640px) {{
        .block-container {{ padding-top: .8rem; padding-left: .7rem; padding-right: .7rem; }}
        .tt-masthead {{ padding: 18px 18px 22px 18px; border-radius: 12px; margin-bottom: 16px; }}
        .tt-masthead .tt-op {{ letter-spacing: 1.5px; font-size: 11px; }}
        .tt-masthead .tt-sub {{ font-size: 12.5px; }}
        .tt-logo-img {{ height: 40px; }}
        .kpilot-logo {{ height: 42px; }}
        /* onglets plus petits : ils tiennent mieux et defilent horizontalement au besoin */
        .stTabs [data-baseweb="tab-list"] {{ gap: 3px; padding: 4px; }}
        .stTabs [data-baseweb="tab"] {{ padding: 7px 11px; font-size: 12.5px; }}
    }}

    /* ================= ECRANS TACTILES (telephone / tablette) =================
       pointer: coarse = ecran controle au doigt -> cibles plus grandes (>= 44px,
       recommandation d'accessibilite tactile). */
    @media (pointer: coarse) {{
        .stDownloadButton button {{ padding: 12px 20px !important; }}
        .stTabs [data-baseweb="tab"] {{ min-height: 44px; display: flex; align-items: center; }}
    }}

    /* Sur ecran sans souris (tactile), on neutralise le survol qui "colle"
       apres un tap (l'effet de levitation resterait bloque). */
    @media (hover: none) {{
        .tt-card:hover {{
            transform: none;
            box-shadow: 0 1px 3px rgba(10,42,74,.06);
            border-color: var(--tt-bordure);
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
#  AUTHENTIFICATION (controle d'acces par role)
# ============================================================================
# Deux acteurs utilisent l'application (voir chapitre 2 du rapport) :
#   - le RESPONSABLE COMMERCIAL : acces complet, y compris l'import mensuel ;
#   - l'ANALYSTE / DIRECTION    : consultation et export uniquement.
# Tant que l'utilisateur n'est pas identifie, on affiche l'ecran de connexion
# et on ARRETE le script (st.stop) : rien d'autre ne s'affiche.

# On prepare la base au demarrage (creation du fichier, des tables et des
# comptes si c'est le premier lancement). L'appel est sans effet ensuite.
bd.initialiser_base()

# Onglets autorises pour chaque role. C'est la traduction en code du
# diagramme des cas d'utilisation : l'analyste ne peut pas injecter de
# donnees, il consulte et exporte.
ONGLETS_PAR_ROLE = {
    "responsable_commercial": [
        "Saisie / Import", "Tableau & mensuel", "Suivi cumule",
        "Detail sous-categories", "Comparaison categories",
        "Analyse regionale", "Prevision & alertes",
    ],
    "analyste_direction": [
        "Tableau & mensuel", "Suivi cumule",
        "Detail sous-categories", "Comparaison categories",
        "Analyse regionale", "Prevision & alertes",
    ],
}


def connecter(utilisateur_trouve):
    """Ouvre la session pour un utilisateur et recharge la page."""
    st.session_state["utilisateur"] = utilisateur_trouve
    st.rerun()


def afficher_page_connexion():
    """Affiche l'ecran de connexion et interrompt le reste de la page.

    L'ecran remplit deux roles a la fois :
      - c'est une vraie porte d'entree (identifiant + mot de passe verifies) ;
      - c'est aussi une page de demonstration : les deux comptes sont affiches
        avec leurs identifiants, et un bouton permet d'entrer directement.
        Un jury peut ainsi essayer les deux profils sans rien taper.
    """
    # --- En-tete : marque et raison d'etre de l'application ---
    logo = (
        f'<img class="kp-login-logo" src="{image_data_uri("assets/logo_kpilot.png")}" alt="KPIlot"/>'
        if os.path.exists("assets/logo_kpilot.png") else '<div class="kp-login-mot">KPIlot</div>'
    )
    st.markdown(
        f'<div class="kp-login-entete">{logo}'
        f'<h1 class="kp-login-titre">Pilotage des ventes</h1>'
        f'<p class="kp-login-sous">Suivi, prevision et alertes sur les indicateurs '
        f'commerciaux &middot; Tunisie Telecom</p></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="kp-login-consigne">Deux profils de demonstration, '
        'avec des droits differents.</p>',
        unsafe_allow_html=True,
    )

    # --- Les deux profils, cote a cote ---
    # Chaque colonne decrit un acteur : qui il est, ce qu'il vient chercher,
    # et ses identifiants. Le bouton connecte directement.
    profils = [
        {
            "identifiant": "s.benammar",
            "mot_de_passe": "Salma2026",
            "nom": "Salma Ben Ammar",
            "fonction": "Responsable commercial",
            "mission": "Suit les objectifs au quotidien, importe les realisations "
                       "du mois et corrige les ecarts.",
            "acces": "7 onglets &middot; import des donnees autorise",
            "couleur": BLEU,
            "couleur_texte": BLEU,
            "initiales": "SB",
        },
        {
            "identifiant": "k.trabelsi",
            "mot_de_passe": "Karim2026",
            "nom": "Karim Trabelsi",
            "fonction": "Analyste - Direction",
            "mission": "Analyse les tendances, la projection annuelle et la "
                       "repartition regionale pour decider.",
            "acces": "6 onglets &middot; consultation et export uniquement",
            "couleur": AMBRE,
            "couleur_texte": AMBRE_TEXTE,
            "initiales": "KT",
        },
    ]

    colonnes = st.columns(2, gap="medium")
    for colonne, profil in zip(colonnes, profils):
        with colonne:
            # st.container(border=True) dessine un VRAI cadre Streamlit. Le
            # bouton place a l'interieur en fait partie : si l'on se contentait
            # d'un <div> en HTML, le bouton s'afficherait en dessous du cadre,
            # visuellement detache de la fiche qu'il accompagne.
            with st.container(border=True):
                st.markdown(
                    f'<div class="kp-profil-tete">'
                    f'<span class="kp-profil-pastille" style="background:{profil["couleur"]};">'
                    f'{profil["initiales"]}</span>'
                    f'<span class="kp-profil-identite">'
                    f'<span class="kp-profil-nom">{profil["nom"]}</span>'
                    f'<span class="kp-profil-fonction" style="color:{profil["couleur_texte"]};">'
                    f'{profil["fonction"]}</span>'
                    f'</span></div>'
                    f'<p class="kp-profil-mission">{profil["mission"]}</p>'
                    f'<p class="kp-profil-acces">{profil["acces"]}</p>'
                    f'<p class="kp-profil-ids">{profil["identifiant"]}'
                    f'<span class="kp-profil-sep">/</span>{profil["mot_de_passe"]}</p>',
                    unsafe_allow_html=True,
                )
                if st.button(f"Entrer comme {profil['nom'].split()[0]}",
                             key=f"demo_{profil['identifiant']}",
                             width="stretch", type="primary"):
                    trouve = bd.verifier_identifiants(profil["identifiant"],
                                                      profil["mot_de_passe"])
                    if trouve:
                        connecter(trouve)
                    else:
                        st.error("Compte de demonstration indisponible.")

    # --- Connexion manuelle, pour montrer que l'authentification est reelle ---
    with st.expander("Se connecter avec un identifiant"):
        # st.form regroupe plusieurs champs : le script n'est relance qu'au clic
        # sur le bouton, et non a chaque frappe au clavier.
        with st.form("formulaire_connexion"):
            nom_saisi = st.text_input("Identifiant")
            mot_de_passe_saisi = st.text_input("Mot de passe", type="password")
            valider = st.form_submit_button("Se connecter", width="stretch")

        if valider:
            utilisateur_trouve = bd.verifier_identifiants(nom_saisi, mot_de_passe_saisi)
            if utilisateur_trouve is None:
                # Message volontairement vague : on ne precise pas si c'est
                # l'identifiant ou le mot de passe qui est faux, pour ne pas
                # aider quelqu'un qui chercherait a deviner un compte.
                st.error("Identifiant ou mot de passe incorrect.")
            else:
                connecter(utilisateur_trouve)

    st.markdown(
        '<p class="kp-login-pied">Les mots de passe sont stockes haches '
        '(PBKDF2-SHA256, 100 000 iterations) avec un sel propre a chaque compte. '
        'Les identifiants ci-dessus sont publics parce qu\'il s\'agit d\'une '
        'demonstration sur donnees simulees.</p>',
        unsafe_allow_html=True,
    )

    st.stop()  # rien de ce qui suit dans app.py n'est execute


# Porte d'entree : si personne n'est connecte, on n'affiche que la connexion.
if "utilisateur" not in st.session_state:
    afficher_page_connexion()

utilisateur = st.session_state["utilisateur"]
role_utilisateur = utilisateur["role"]
onglets_autorises = ONGLETS_PAR_ROLE[role_utilisateur]

# ---- Bandeau d'en-tete ----
# Marque KPIlot (version blanche posee sur le bandeau fonce) ; repli sur le titre
# texte si l'image n'est pas encore disponible.
if os.path.exists("assets/logo_kpilot_blanc.png"):
    marque_kpilot = (
        f'<img class="kpilot-logo" src="{image_data_uri("assets/logo_kpilot_blanc.png")}" '
        f'alt="KPIlot"/>'
    )
else:
    marque_kpilot = '<h1 class="tt-title">KPIlot</h1>'

st.markdown(
    f"""
    <div class="tt-masthead">
        <div class="tt-brand">
            {marque_kpilot}
            <span class="tt-op-sep"></span>
            {logo_html()}
        </div>
        <p class="tt-sub">Piloter les ventes par la donnee &middot; suivi, prevision et alertes &middot; Tunisie Telecom</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
#  Chargement et calcul des KPI (meme logique que calcul_kpi.py)
# ============================================================================
# Source des ventes : soit un fichier importe par l'utilisateur (mode reel),
# soit le fichier de demonstration (mode demo). Quand on depose un fichier dans
# l'onglet "Saisie / Import", il est memorise dans st.session_state ; a chaque
# reexecution du script, Streamlit repasse ici et utilise ces donnees a la place.
# Les ventes et les objectifs sont desormais lus dans la BASE DE DONNEES
# (et non plus directement dans les CSV). L'import mensuel ecrit dans cette
# meme base : le tableau de bord reflete donc toujours son contenu reel.
ventes = bd.lire_ventes()
objectifs = bd.lire_objectifs()

# Un import a-t-il deja eu lieu pendant cette session ? (sert a l'affichage)
mode_reel = "dernier_import" in st.session_state
source_donnees = (
    st.session_state.get("dernier_import", "base de donnees (data/kpilot.db)")
    if mode_reel else "base de donnees (data/kpilot.db)"
)

prevision = charger_si_existe("data/prevision.csv")
atteinte = charger_si_existe("data/atteinte_objectif.csv")
anomalies = charger_si_existe("data/anomalies.csv")
validation = charger_si_existe("data/validation_modele.csv")

# Preparation des ventes (dates + annee/mois) et calcul des KPI,
# via le module partage kpi.py (meme logique que calcul_kpi.py).
ventes = preparer_ventes(ventes)
kpi = calculer_kpi(ventes, objectifs)

# ============================================================================
#  Selecteurs (barre laterale)
# ============================================================================
# ---- Identite de l'utilisateur connecte + deconnexion ----
st.sidebar.markdown(
    f'<div class="kp-qui">'
    f'<div class="kp-qui-nom">{utilisateur["nom_complet"]}</div>'
    f'<div class="kp-qui-role">'
    f'{bd.LIBELLE_ROLE.get(role_utilisateur, role_utilisateur)}</div>'
    f'</div>',
    unsafe_allow_html=True,
)
if st.sidebar.button("Se deconnecter"):
    # On vide la session : l'utilisateur revient a l'ecran de connexion.
    st.session_state.clear()
    st.rerun()
st.sidebar.divider()

st.sidebar.header("Filtres")
categories = kpi["categorie"].unique()
categorie_choisie = st.sidebar.selectbox("Categorie", categories)

annees_disponibles = kpi.loc[kpi["categorie"] == categorie_choisie, "annee"].unique()
annee_choisie = st.sidebar.selectbox("Annee", sorted(annees_disponibles))

kpi_filtre = kpi[(kpi["categorie"] == categorie_choisie) & (kpi["annee"] == annee_choisie)]
kpi_annee = kpi[kpi["annee"] == annee_choisie]

# ============================================================================
#  Ecran d'accueil : IL DEPEND DU ROLE
# ============================================================================
# Le responsable commercial et la direction ne se posent pas la meme question.
#
#   - le responsable, chaque matin : "qu'est-ce qui est en retard, et que
#     dois-je faire ce mois-ci ?"   -> un POSTE DE PILOTAGE, tourne vers l'action ;
#   - la direction, ponctuellement : "ou atterrit-on cette annee, et peut-on
#     s'y fier ?"                   -> une NOTE DE SYNTHESE, tournee vers la decision.
#
# Les onglets d'analyse restent communs (les memes chiffres doivent rester
# consultables par les deux), mais l'entree dans l'application differe.

# --- Chiffres communs aux deux ecrans ---
total_realise = kpi_filtre["ventes_reelles"].sum()
total_objectif = kpi_filtre["objectif_mensuel"].sum()
taux_global = round(total_realise / total_objectif * 100, 1) if total_objectif != 0 else None
ecart_global = total_realise - total_objectif

# Situation cumulee de TOUTES les categories sur l'annee choisie
alertes = (
    kpi_annee.groupby("categorie")[["ventes_reelles", "objectif_mensuel"]]
    .sum()
    .reset_index()
)
alertes["taux"] = alertes.apply(
    lambda r: round(r["ventes_reelles"] / r["objectif_mensuel"] * 100, 1)
    if r["objectif_mensuel"] else None,
    axis=1,
)
alertes["manque"] = alertes["objectif_mensuel"] - alertes["ventes_reelles"]

# Dernier mois pour lequel on a des ventes, et mois restants dans l'annee
mois_connus = int(kpi_annee["mois"].max()) if len(kpi_annee) else 0
mois_restants = max(12 - mois_connus, 0)


def titre_ecran(titre, sous_titre):
    """Titre de l'ecran d'accueil, avec une phrase qui dit a qui il s'adresse."""
    st.markdown(
        f'<div class="kp-ecran"><h2 class="kp-ecran-titre">{titre}</h2>'
        f'<p class="kp-ecran-sous">{sous_titre}</p></div>',
        unsafe_allow_html=True,
    )


def bandeau(ton, etiquette, phrase, detail=""):
    """Bandeau de tete : la seule information a retenir en ouvrant l'ecran.

    'ton' vaut 'alerte', 'attention' ou 'ok' et determine la couleur.
    """
    # Deux teintes : une pour le trait (aplat, contraste non critique), une
    # pour l'etiquette en petites capitales (contraste critique).
    couleur = {"alerte": ROUGE, "attention": ORANGE, "ok": VERT}.get(ton, BLEU)
    couleur_texte = {"alerte": ROUGE, "attention": ORANGE_TEXTE,
                     "ok": VERT_TEXTE}.get(ton, BLEU)
    st.markdown(
        f'<div class="kp-bandeau" style="border-color:{couleur};">'
        f'<div class="kp-bandeau-etiquette" style="color:{couleur_texte};">{etiquette}</div>'
        f'<div class="kp-bandeau-phrase">{phrase}</div>'
        + (f'<div class="kp-bandeau-detail">{detail}</div>' if detail else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def offre_qui_decroche(categorie, annee, mois_reference):
    """Sous-categorie dont la PART dans la categorie recule le plus.

    On compare la part de chaque offre sur le dernier mois connu a sa part
    moyenne depuis le debut de l'annee. Celle qui recule le plus est celle
    sur laquelle il faut agir en priorite.
    Renvoie (nom, evolution en %) ou None si le calcul n'est pas possible.
    """
    lignes = ventes[(ventes["annee"] == annee) & (ventes["categorie"] == categorie)]
    if lignes.empty or lignes["quantite"].sum() == 0:
        return None
    part_moyenne = lignes.groupby("sous_categorie")["quantite"].sum() / lignes["quantite"].sum()

    dernier_mois = lignes[lignes["mois"] == mois_reference]
    if dernier_mois.empty or dernier_mois["quantite"].sum() == 0:
        return None
    part_dernier = dernier_mois.groupby("sous_categorie")["quantite"].sum() / dernier_mois["quantite"].sum()

    # Protection : on ne divise que par les parts moyennes non nulles
    part_moyenne = part_moyenne[part_moyenne > 0]
    evolution = ((part_dernier - part_moyenne) / part_moyenne * 100).dropna().sort_values()
    if evolution.empty:
        return None
    return evolution.index[0], round(float(evolution.iloc[0]), 1)


def ecran_responsable():
    """Accueil du RESPONSABLE COMMERCIAL : ou agir, et a quel rythme."""
    titre_ecran(
        "Poste de pilotage",
        f"Ce qu'il faut regarder aujourd'hui pour tenir les objectifs {annee_choisie}.",
    )

    en_retard = alertes[alertes["manque"] > 0].sort_values("manque", ascending=False)

    if len(en_retard) == 0:
        bandeau("ok", "Situation",
                f"Toutes les categories sont au niveau de leur objectif cumule {annee_choisie}.",
                "Rien ne demande d'action corrective a ce stade.")
        rythme_requis, categorie_prio = 0, None
    else:
        prioritaire = en_retard.iloc[0]
        categorie_prio = prioritaire["categorie"]
        manque = int(prioritaire["manque"])
        # -(-a // b) = division arrondie vers le HAUT : on ne veut pas
        # sous-estimer l'effort a fournir.
        rythme_requis = -(-manque // mois_restants) if mois_restants else manque
        bandeau(
            "alerte" if prioritaire["taux"] < 90 else "attention",
            "Priorite",
            f"{categorie_prio} : il manque <strong>{manque:,}</strong> ventes "
            f"sur l'objectif {annee_choisie}.".replace(",", " "),
            f"Soit {rythme_requis} ventes par mois sur les {mois_restants} mois restants."
            if mois_restants else "L'annee est terminee : l'ecart ne peut plus etre rattrape.",
        )

    # --- Trois indicateurs qui disent QUOI FAIRE (et non ou l'on en est) ---
    col_a, col_b, col_c = st.columns(3)
    col_a.markdown(
        carte_kpi("Rythme a tenir",
                  f"{rythme_requis}",
                  "ventes / mois pour rattraper" if rythme_requis else "objectif deja tenu",
                  couleur=ROUGE if rythme_requis else VERT, icone="objectif"),
        unsafe_allow_html=True,
    )

    decrochage = offre_qui_decroche(categorie_prio or categorie_choisie,
                                    annee_choisie, mois_connus)
    if decrochage:
        offre, evolution = decrochage
        col_b.markdown(
            carte_kpi("Offre qui decroche", offre,
                      f"{evolution:+.0f} % de part le dernier mois",
                      couleur=ORANGE, icone="ventes"),
            unsafe_allow_html=True,
        )
    else:
        col_b.markdown(
            carte_kpi("Offre qui decroche", "-", "donnees insuffisantes",
                      couleur=GRIS, icone="ventes"),
            unsafe_allow_html=True,
        )

    col_c.markdown(
        carte_kpi("Temps restant", f"{mois_restants}",
                  f"mois avant la fin {annee_choisie}",
                  couleur=BLEU, icone="annuel"),
        unsafe_allow_html=True,
    )

    # --- Etat categorie par categorie ---
    st.write("")
    st.subheader(f"Etat des categories - cumul {annee_choisie}")
    for _, ligne_alerte in alertes.iterrows():
        manque = int(ligne_alerte["manque"])
        taux = ligne_alerte["taux"]
        nom = ligne_alerte["categorie"]
        if taux is None:
            st.info(f"{nom} : pas d'objectif defini.")
        elif taux >= 100:
            st.success(f"{nom} : objectif atteint a ce stade ({taux} %).")
        elif taux >= 90:
            st.warning(f"{nom} : proche de l'objectif ({taux} %) - il manque {manque} ventes.")
        else:
            st.error(f"{nom} : en retard ({taux} %) - il manque {manque} ventes.")

    st.caption(
        "Le fichier des realisations du mois se depose dans l'onglet "
        "**Saisie / Import** : les indicateurs ci-dessus se recalculent aussitot."
    )


def ecran_analyste():
    """Accueil de l'ANALYSTE / DIRECTION : ou atterrit-on, et est-ce fiable."""
    titre_ecran(
        "Note de synthese",
        f"Projection de fin d'annee {annee_choisie}, fiabilite du modele et lecture regionale.",
    )

    # --- Atterrissage annuel, toutes categories confondues ---
    atterrissage = None
    if atteinte is not None:
        lignes_annee = atteinte[atteinte["annee"] == annee_choisie]
        if len(lignes_annee):
            estime = int(lignes_annee["total_estime"].sum())
            vise = int(lignes_annee["objectif_annuel"].sum())
            taux_atterrissage = round(estime / vise * 100, 1) if vise else None
            atterrissage = (estime, vise, taux_atterrissage)

    if atterrissage:
        estime, vise, taux_atterrissage = atterrissage
        ton = "ok" if taux_atterrissage >= 100 else ("attention" if taux_atterrissage >= 90 else "alerte")
        bandeau(
            ton, "Atterrissage projete",
            f"<strong>{estime:,}</strong> ventes attendues fin {annee_choisie} "
            f"pour {vise:,} visees, soit <strong>{taux_atterrissage} %</strong>.".replace(",", " "),
            f"Ecart projete : {vise - estime:,} ventes.".replace(",", " ")
            if vise > estime else "Objectif annuel projete comme atteint.",
        )
    else:
        bandeau("attention", "Atterrissage projete",
                "Projection indisponible pour cette annee.",
                "Lancer python prediction_atteinte.py pour la produire.")

    # --- Trois indicateurs de DECISION ---
    col_a, col_b, col_c = st.columns(3)

    if validation is not None and len(validation):
        mape = validation["erreur_pct"].mean()
        fiabilite = round(100 - mape, 1)
        col_a.markdown(
            carte_kpi("Fiabilite du modele", f"{fiabilite} %",
                      f"erreur moyenne {mape:.1f} % (backtesting)",
                      couleur=couleur_selon_taux(fiabilite), icone="taux"),
            unsafe_allow_html=True,
        )
    else:
        col_a.markdown(
            carte_kpi("Fiabilite du modele", "-", "validation non calculee",
                      couleur=GRIS, icone="taux"),
            unsafe_allow_html=True,
        )

    ventes_annee = ventes[ventes["annee"] == annee_choisie]
    if len(ventes_annee) and "region" in ventes_annee.columns:
        par_region = ventes_annee.groupby("region")["quantite"].sum().sort_values(ascending=False)
        part = par_region.iloc[0] / par_region.sum() * 100
        col_b.markdown(
            carte_kpi("Region motrice", par_region.index[0],
                      f"{part:.1f} % du volume national",
                      couleur=BLEU, icone="ventes"),
            unsafe_allow_html=True,
        )
    else:
        col_b.markdown(
            carte_kpi("Region motrice", "-", "pas de donnee regionale",
                      couleur=GRIS, icone="ventes"),
            unsafe_allow_html=True,
        )

    # Croissance entre les deux dernieres annees COMPLETES
    par_annee = ventes.groupby("annee")["quantite"].sum()
    annees_completes = [a for a in par_annee.index if a < annee_choisie]
    if len(annees_completes) >= 2:
        recente, precedente = annees_completes[-1], annees_completes[-2]
        croissance = (par_annee[recente] / par_annee[precedente] - 1) * 100
        col_c.markdown(
            carte_kpi("Croissance annuelle", f"{croissance:+.1f} %",
                      f"{precedente} vers {recente}",
                      couleur=VERT if croissance >= 0 else ROUGE, icone="annuel"),
            unsafe_allow_html=True,
        )
    else:
        col_c.markdown(
            carte_kpi("Croissance annuelle", "-", "historique trop court",
                      couleur=GRIS, icone="annuel"),
            unsafe_allow_html=True,
        )

    # --- Projection detaillee par categorie ---
    if atteinte is not None:
        lignes_annee = atteinte[atteinte["annee"] == annee_choisie]
        if len(lignes_annee):
            st.write("")
            st.subheader(f"Projection par categorie - {annee_choisie}")
            tableau = lignes_annee[[
                "categorie", "realise_connu", "prevu_restant",
                "total_estime", "objectif_annuel", "taux_estime_pct",
            ]].rename(columns={
                "categorie": "Categorie", "realise_connu": "Realise connu",
                "prevu_restant": "Prevu restant", "total_estime": "Total estime",
                "objectif_annuel": "Objectif annuel", "taux_estime_pct": "Taux estime (%)",
            })
            st.dataframe(tableau, width="stretch", hide_index=True)

    st.caption(
        "Les onglets ci-dessous permettent d'entrer dans le detail : comparaison "
        "des categories, analyse regionale et prevision mois par mois."
    )


# --- Aiguillage : chaque role recoit son ecran ---
if role_utilisateur == "responsable_commercial":
    ecran_responsable()
else:
    ecran_analyste()

# --- Exports, communs aux deux roles ---
st.write("")
colonne_csv, colonne_pdf = st.columns(2)
colonne_csv.download_button(
    label="Exporter le KPI filtre (CSV)",
    data=kpi_filtre.to_csv(index=False).encode("utf-8"),
    file_name=f"kpi_{categorie_choisie}_{annee_choisie}.csv",
    mime="text/csv",
    width="stretch",
)
rapport_pdf = generer_rapport_pdf(
    categorie_choisie, annee_choisie, total_realise, total_objectif,
    taux_global, ecart_global, alertes,
)
colonne_pdf.download_button(
    label="Exporter le rapport (PDF)",
    data=rapport_pdf,
    file_name=f"rapport_{categorie_choisie}_{annee_choisie}.pdf",
    mime="application/pdf",
    width="stretch",
)


# ============================================================================
#  Onglets
# ============================================================================
# Les onglets affiches dependent du ROLE de l'utilisateur connecte.
# st.tabs recoit donc la liste calculee plus haut (ONGLETS_PAR_ROLE), et on
# range les onglets obtenus dans un dictionnaire pour les retrouver par nom.
liste_onglets = st.tabs(onglets_autorises)
onglets = dict(zip(onglets_autorises, liste_onglets))

# --- Onglet 0 : interface d'entree (import du fichier mensuel de realisations) ---
# L'import est reserve au responsable commercial : pour l'analyste,
# cet onglet n'existe tout simplement pas (controle d'acces par role).
if "Saisie / Import" in onglets:
    with onglets["Saisie / Import"]:
        st.subheader("Import des realisations du mois")
        st.write(
            "Chaque mois, deposez ici le fichier des ventes reelles (Excel .xlsx ou "
            "CSV). Les lignes sont **enregistrees dans la base de donnees** et les "
            "KPI sont recalcules immediatement."
        )

        # Etat actuel de la base : combien de lignes contient-elle ?
        totaux_base = bd.compter_lignes()
        colonne_v, colonne_o, colonne_u = st.columns(3)
        colonne_v.metric("Ventes en base", f"{totaux_base['ventes']:,}".replace(",", " "))
        colonne_o.metric("Objectifs en base", totaux_base["objectifs"])
        colonne_u.metric("Comptes utilisateurs", totaux_base["utilisateurs"])

        if mode_reel:
            st.success(f"Dernier import : **{source_donnees}**.")
        else:
            st.info("Aucun import effectue pendant cette session.")

        # Rappel du format attendu + modele telechargeable (extrait des donnees demo)
        st.markdown(
            "**Format attendu** (une ligne par vente) : "
            + ", ".join(f"`{c}`" for c in COLONNES_ATTENDUES)
        )
        modele = pd.DataFrame(
            {
                "date": ["2026-07-01", "2026-07-01"],
                "categorie": ["Internet Fixe", "Mobile"],
                "sous_categorie": ["ADSL", "Data"],
                "quantite": [6, 12],
                "region": ["Sfax", "Grand Tunis"],
            }
        )
        st.download_button(
            "Telecharger un modele vierge (CSV)",
            data=modele.to_csv(index=False).encode("utf-8"),
            file_name="modele_realisations.csv",
            mime="text/csv",
        )

        st.divider()

        # Le bouton d'import proprement dit.
        # On lui donne une "cle" (key) dont le numero peut changer : en incrementant
        # ce numero (bouton "Revenir aux donnees de demo"), Streamlit recree un bouton
        # VIDE, ce qui evite que l'ancien fichier soit reimporte aussitot apres.
        if "uploader_key" not in st.session_state:
            st.session_state["uploader_key"] = 0
        fichier = st.file_uploader(
            "Deposer le fichier des realisations",
            type=["xlsx", "xls", "csv"],
            key=f"upload_{st.session_state['uploader_key']}",
        )

        if fichier is not None:
            try:
                df_importe = lire_fichier_importe(fichier)
            except Exception as erreur:  # fichier illisible / corrompu
                st.error(f"Impossible de lire le fichier : {erreur}")
            else:
                valide, message = valider_ventes(df_importe)
                if not valide:
                    st.error(message)
                else:
                    st.success(message)
                    st.caption("Apercu des premieres lignes du fichier importe :")
                    st.dataframe(df_importe.head(), width="stretch")
                    # On ecrit dans la base, une seule fois par fichier.
                    # Le test sur le nom evite une boucle de reexecution infinie :
                    # une fois le fichier enregistre, on ne recommence pas.
                    if st.session_state.get("nom_fichier") != fichier.name:
                        resume = bd.importer_ventes(df_importe)
                        mois_lisibles = ", ".join(
                            f"{mois:02d}/{annee}" for annee, mois in resume["mois"]
                        )
                        st.session_state["nom_fichier"] = fichier.name
                        st.session_state["dernier_import"] = (
                            f"{fichier.name} ({mois_lisibles})"
                        )
                        st.session_state["resume_import"] = resume
                        st.rerun()

        # Compte rendu de la derniere ecriture en base
        if "resume_import" in st.session_state:
            resume = st.session_state["resume_import"]
            st.info(
                f"Ecriture en base : {resume['ajoutees']} ligne(s) ajoutee(s), "
                f"{resume['supprimees']} ancienne(s) ligne(s) remplacee(s) pour "
                f"le(s) mois concerne(s). Reimporter le meme fichier ne cree donc "
                f"aucun doublon."
            )

        # Bouton pour remettre la base dans son etat de demonstration
        st.divider()
        if st.button("Reinitialiser la base (donnees de demonstration)"):
            bd.reinitialiser_depuis_csv()
            st.session_state.pop("nom_fichier", None)
            st.session_state.pop("dernier_import", None)
            st.session_state.pop("resume_import", None)
            # On change la cle du bouton d'upload -> il se vide vraiment,
            # sinon l'ancien fichier serait reimporte immediatement.
            st.session_state["uploader_key"] += 1
            st.rerun()

# --- Onglet 1 : tableau KPI + histogramme mensuel ---
with onglets["Tableau & mensuel"]:
    st.subheader(f"Tableau KPI - {categorie_choisie} {annee_choisie}")
    st.dataframe(kpi_filtre, width="stretch")

    kpi_graphique = kpi_filtre.melt(
        id_vars=["mois"],
        value_vars=["ventes_reelles", "objectif_mensuel"],
        var_name="type",
        value_name="valeur",
    )
    kpi_graphique["type"] = kpi_graphique["type"].replace(
        {"ventes_reelles": "Realise", "objectif_mensuel": "Objectif"}
    )

    st.subheader(f"Realise vs Objectif par mois - {categorie_choisie} {annee_choisie}")
    figure = px.bar(
        kpi_graphique,
        x="mois",
        y="valeur",
        color="type",
        barmode="group",
        color_discrete_map={"Realise": BLEU, "Objectif": GRIS},
        labels={"mois": "Mois", "valeur": "Quantite", "type": "Legende"},
    )
    figure.update_layout(template="plotly_white")
    st.plotly_chart(figure, width="stretch")

    # --- Ventes moyennes par jour de la semaine ---
    # On exploite ici la finesse JOURNALIERE des donnees (le reste du dashboard
    # ne montre que du mensuel). Objectif : voir quels jours vendent le plus.
    st.subheader(f"Ventes moyennes par jour de la semaine - {categorie_choisie} {annee_choisie}")

    JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    ventes_cat_annee = ventes[
        (ventes["categorie"] == categorie_choisie) & (ventes["annee"] == annee_choisie)
    ]
    # 1) total vendu chaque JOUR (toutes sous-categories confondues)
    total_par_jour = ventes_cat_annee.groupby("date")["quantite"].sum().reset_index()
    # 2) .dt.dayofweek donne le jour : 0 = lundi ... 6 = dimanche
    total_par_jour["jour_num"] = total_par_jour["date"].dt.dayofweek
    # 3) moyenne par jour de semaine (comparaison equitable : ~52 lundis, etc.)
    moyenne_par_jour = total_par_jour.groupby("jour_num")["quantite"].mean().reset_index()
    moyenne_par_jour["jour"] = moyenne_par_jour["jour_num"].map(lambda i: JOURS[i])
    moyenne_par_jour["quantite"] = moyenne_par_jour["quantite"].round(1)

    figure_jours = px.bar(
        moyenne_par_jour,
        x="jour",
        y="quantite",
        color_discrete_sequence=[BLEU],
        category_orders={"jour": JOURS},  # garde l'ordre Lundi -> Dimanche
        labels={"jour": "Jour", "quantite": "Ventes moyennes / jour"},
    )
    figure_jours.update_layout(template="plotly_white")
    st.plotly_chart(figure_jours, width="stretch")

# --- Onglet 2 : suivi cumule ---
with onglets["Suivi cumule"]:
    kpi_cumule = kpi_filtre.sort_values("mois").copy()
    kpi_cumule["ventes_cumulees"] = kpi_cumule["ventes_reelles"].cumsum()
    kpi_cumule["objectif_cumule"] = kpi_cumule["objectif_mensuel"].cumsum()

    kpi_cumule_graphique = kpi_cumule.melt(
        id_vars=["mois"],
        value_vars=["ventes_cumulees", "objectif_cumule"],
        var_name="type",
        value_name="valeur",
    )
    kpi_cumule_graphique["type"] = kpi_cumule_graphique["type"].replace(
        {"ventes_cumulees": "Realise cumule", "objectif_cumule": "Objectif cumule"}
    )

    st.subheader(f"Suivi cumule - {categorie_choisie} {annee_choisie}")
    figure_cumule = px.line(
        kpi_cumule_graphique,
        x="mois",
        y="valeur",
        color="type",
        markers=True,
        color_discrete_map={"Realise cumule": BLEU, "Objectif cumule": ROUGE},
        labels={"mois": "Mois", "valeur": "Quantite cumulee", "type": "Legende"},
    )
    figure_cumule.update_layout(template="plotly_white")
    st.plotly_chart(figure_cumule, width="stretch")

# --- Onglet 3 : detail par sous-categorie ---
with onglets["Detail sous-categories"]:
    sous_categories_disponibles = sorted(
        ventes.loc[ventes["categorie"] == categorie_choisie, "sous_categorie"].unique()
    )
    sous_categories_choisies = st.multiselect(
        "Filtrer les sous-categories",
        sous_categories_disponibles,
        default=sous_categories_disponibles,
    )

    ventes_sous_categorie = (
        ventes[
            (ventes["categorie"] == categorie_choisie)
            & (ventes["annee"] == annee_choisie)
            & (ventes["sous_categorie"].isin(sous_categories_choisies))
        ]
        .groupby(["mois", "sous_categorie"])["quantite"]
        .sum()
        .reset_index()
    )

    st.subheader(f"Ventes reelles par sous-categorie - {categorie_choisie} {annee_choisie}")
    figure_sous_categorie = px.bar(
        ventes_sous_categorie,
        x="mois",
        y="quantite",
        color="sous_categorie",
        barmode="group",
        labels={"mois": "Mois", "quantite": "Quantite", "sous_categorie": "Sous-categorie"},
    )
    figure_sous_categorie.update_layout(template="plotly_white")
    st.plotly_chart(figure_sous_categorie, width="stretch")

# --- Onglet 4 : comparaison des categories ---
with onglets["Comparaison categories"]:
    st.subheader(f"Realise par categorie et par mois - {annee_choisie}")
    figure_comparaison = px.bar(
        kpi_annee,
        x="mois",
        y="ventes_reelles",
        color="categorie",
        barmode="group",
        color_discrete_map={"Internet Fixe": BLEU, "Mobile": NUIT},
        labels={"mois": "Mois", "ventes_reelles": "Quantite", "categorie": "Categorie"},
    )
    figure_comparaison.update_layout(template="plotly_white")
    st.plotly_chart(figure_comparaison, width="stretch")

    st.subheader(f"Taux de realisation par categorie et par mois - {annee_choisie}")
    figure_taux_comparaison = px.line(
        kpi_annee,
        x="mois",
        y="taux_atteinte_pct",
        color="categorie",
        markers=True,
        color_discrete_map={"Internet Fixe": BLEU, "Mobile": NUIT},
        labels={"mois": "Mois", "taux_atteinte_pct": "Taux de realisation (%)", "categorie": "Categorie"},
    )
    figure_taux_comparaison.update_layout(template="plotly_white")
    st.plotly_chart(figure_taux_comparaison, width="stretch")

    # --- Evolution pluriannuelle (a periode comparable : 1er semestre) ---
    # 2026 est incomplet (jan-juin), donc on compare le MEME semestre chaque
    # annee pour eviter tout biais. Montre si les ventes progressent.
    st.subheader("Evolution des ventes du 1er semestre (janvier a juin), par annee")
    premier_semestre = ventes[ventes["mois"].between(1, 6)]
    evolution = (
        premier_semestre.groupby(["annee", "categorie"])["quantite"].sum().reset_index()
    )
    figure_evolution = px.line(
        evolution,
        x="annee",
        y="quantite",
        color="categorie",
        markers=True,
        color_discrete_map={"Internet Fixe": BLEU, "Mobile": NUIT},
        labels={"annee": "Annee", "quantite": "Ventes (jan-juin)", "categorie": "Categorie"},
    )
    figure_evolution.update_layout(template="plotly_white")
    figure_evolution.update_xaxes(dtick=1)  # afficher des annees entieres
    st.plotly_chart(figure_evolution, width="stretch")
    st.caption(
        "Comparaison a periode identique (janvier-juin) pour chaque annee, "
        "afin d'eviter le biais du 2026 incomplet."
    )

# --- Onglet 5 : analyse regionale ---
with onglets["Analyse regionale"]:
    # Les objectifs n'existent pas au niveau region (comme pour les
    # sous-categories) : on montre donc uniquement le realise par region.
    ventes_region_annee = ventes[
        (ventes["categorie"] == categorie_choisie) & (ventes["annee"] == annee_choisie)
    ]

    # --- Total des ventes par region (barres horizontales, triees) ---
    ventes_par_region = (
        ventes_region_annee.groupby("region")["quantite"]
        .sum()
        .reset_index()
        .sort_values("quantite", ascending=True)  # la plus grande finit en haut
    )

    # Carte : region qui vend le plus
    if len(ventes_par_region) > 0:
        region_top = ventes_par_region.iloc[-1]
        col_a, col_b = st.columns(2)
        col_a.markdown(
            carte_kpi("Region la plus performante", region_top["region"], icone="ventes"),
            unsafe_allow_html=True,
        )
        col_b.markdown(
            carte_kpi(
                "Ventes de cette region",
                f"{int(region_top['quantite']):,}".replace(",", " "),
                "sur la periode",
                couleur=GRIS,
                icone="annuel",
            ),
            unsafe_allow_html=True,
        )
        st.write("")

    st.subheader(f"Ventes par region - {categorie_choisie} {annee_choisie}")
    figure_region = px.bar(
        ventes_par_region,
        x="quantite",
        y="region",
        orientation="h",
        color_discrete_sequence=[BLEU],
        labels={"quantite": "Ventes", "region": "Region"},
    )
    figure_region.update_layout(template="plotly_white")
    st.plotly_chart(figure_region, width="stretch")

    # --- Repartition mensuelle empilee par region ---
    st.subheader(f"Repartition mensuelle par region - {annee_choisie}")
    ventes_region_mois = (
        ventes_region_annee.groupby(["mois", "region"])["quantite"].sum().reset_index()
    )
    figure_region_mois = px.bar(
        ventes_region_mois,
        x="mois",
        y="quantite",
        color="region",
        barmode="stack",
        labels={"mois": "Mois", "quantite": "Ventes", "region": "Region"},
    )
    figure_region_mois.update_layout(template="plotly_white")
    st.plotly_chart(figure_region_mois, width="stretch")

    # --- Tableau des realisations par region (une ligne = une region) ---
    # Tableau croise : regions en lignes, mois en colonnes, + une colonne Total.
    # Ce sont les ventes REELLEMENT realisees (les "realisations"), declinees
    # par region comme demande.
    st.subheader(f"Tableau des realisations par region - {categorie_choisie} {annee_choisie}")
    tableau_realisations = ventes_region_annee.pivot_table(
        index="region", columns="mois", values="quantite", aggfunc="sum", fill_value=0
    )
    tableau_realisations["Total"] = tableau_realisations.sum(axis=1)
    tableau_realisations = tableau_realisations.sort_values("Total", ascending=False)
    st.dataframe(tableau_realisations, width="stretch")

    # Bouton pour telecharger ces realisations au format CSV
    realisations_csv = (
        ventes_region_annee.groupby(["region", "mois"])["quantite"]
        .sum()
        .reset_index()
        .rename(columns={"quantite": "realisation"})
        .to_csv(index=False)
        .encode("utf-8")
    )
    st.download_button(
        "Telecharger les realisations par region (CSV)",
        data=realisations_csv,
        file_name=f"realisations_{categorie_choisie}_{annee_choisie}.csv",
        mime="text/csv",
    )

    st.caption(
        "Note : la dimension regionale est simulee (ajoutee via ajouter_region.py) "
        "pour demontrer la capacite d'analyse geographique."
    )

# --- Onglet 6 : prevision + probabilite d'atteinte + anomalies ---
with onglets["Prevision & alertes"]:

    # ===== A. Prevision Prophet =====
    st.subheader(f"Prevision des ventes - {categorie_choisie}")
    if prevision is None:
        st.warning("Fichier data/prevision.csv absent. Lance d'abord : python forecast.py")
    else:
        prevision_categorie = prevision[prevision["categorie"] == categorie_choisie].copy()
        prevision_categorie["ds"] = pd.to_datetime(prevision_categorie["ds"])

        ventes_reelles_mois = (
            ventes[ventes["categorie"] == categorie_choisie]
            .groupby(pd.Grouper(key="date", freq="MS"))["quantite"]
            .sum()
            .reset_index()
        )

        figure_prevision = go.Figure()
        figure_prevision.add_trace(
            go.Scatter(
                x=prevision_categorie["ds"], y=prevision_categorie["prevision_max"],
                line=dict(width=0), showlegend=False, hoverinfo="skip",
            )
        )
        figure_prevision.add_trace(
            go.Scatter(
                x=prevision_categorie["ds"], y=prevision_categorie["prevision_min"],
                fill="tonexty", fillcolor="rgba(0, 114, 188, 0.15)", line=dict(width=0),
                name="Intervalle de confiance", hoverinfo="skip",
            )
        )
        figure_prevision.add_trace(
            go.Scatter(
                x=prevision_categorie["ds"], y=prevision_categorie["prevision"],
                line=dict(color=BLEU, width=2), name="Prevision",
            )
        )
        figure_prevision.add_trace(
            go.Scatter(
                x=ventes_reelles_mois["date"], y=ventes_reelles_mois["quantite"],
                mode="markers", marker=dict(color=NUIT, size=6), name="Ventes reelles",
            )
        )
        figure_prevision.update_layout(
            template="plotly_white", xaxis_title="Mois", yaxis_title="Quantite mensuelle"
        )
        st.plotly_chart(figure_prevision, width="stretch")
        st.caption(
            "Points bleu nuit = ventes reelles connues. Ligne bleue = prevision Prophet. "
            "Zone bleue = incertitude du modele (intervalle de confiance)."
        )

    # ===== B. Probabilite d'atteindre l'objectif annuel =====
    st.subheader(f"Atteinte de l'objectif annuel - {categorie_choisie}")
    if atteinte is None:
        st.warning("Fichier data/atteinte_objectif.csv absent. Lance d'abord : python prediction_atteinte.py")
    else:
        atteinte_categorie = atteinte[atteinte["categorie"] == categorie_choisie]
        for _, ligne in atteinte_categorie.iterrows():
            st.markdown(f"**Annee {int(ligne['annee'])}**")
            couleur_ligne = couleur_selon_taux(ligne["taux_estime_pct"])
            col1, col2, col3 = st.columns(3)
            col1.markdown(
                carte_kpi(
                    "Total estime",
                    f"{int(ligne['total_estime']):,}".replace(",", " "),
                    icone="annuel",
                ),
                unsafe_allow_html=True,
            )
            col2.markdown(
                carte_kpi(
                    "Objectif annuel",
                    f"{int(ligne['objectif_annuel']):,}".replace(",", " "),
                    couleur=GRIS,
                    icone="objectif",
                ),
                unsafe_allow_html=True,
            )
            col3.markdown(
                carte_kpi(
                    "Taux estime",
                    f"{ligne['taux_estime_pct']} %",
                    f"proba : {ligne['probabilite_atteinte_pct']} %",
                    couleur=couleur_ligne,
                    extra_html=barres_signal(ligne["taux_estime_pct"], couleur_ligne),
                    icone="taux",
                ),
                unsafe_allow_html=True,
            )
            st.write("")
            # Jauge visuelle du taux d'atteinte annuel (compteur)
            st.plotly_chart(
                jauge_taux(ligne["taux_estime_pct"], f"Taux d'atteinte estime - {int(ligne['annee'])}"),
                width="stretch",
            )
            if ligne["ecart_a_combler"] > 0:
                st.info(
                    f"Il manque environ {int(ligne['ecart_a_combler'])} ventes pour atteindre l'objectif "
                    f"(probabilite estimee : {ligne['probabilite_atteinte_pct']} %)."
                )
            else:
                st.success(
                    f"Objectif atteint ({int(abs(ligne['ecart_a_combler']))} ventes au-dela de la cible)."
                )

            # Lecture de la probabilite : sur des donnees simulees tres
            # regulieres, Prophet produit un intervalle de confiance etroit.
            # La loi normale bascule alors brutalement vers 0 % ou 100 % des
            # que l'objectif sort de cette fourchette : la probabilite devient
            # un "tout ou rien" peu informatif. L'indicateur a lire est le
            # TAUX estime, qui dit de combien on s'approche de la cible.
            if ligne["probabilite_atteinte_pct"] in (0.0, 100.0):
                st.caption(
                    "Lecture : l'historique simule est tres regulier, donc la fourchette "
                    "d'incertitude de Prophet est etroite et la probabilite bascule vers "
                    "0 % ou 100 % des que l'objectif sort de cette fourchette. L'indicateur "
                    f"a retenir ici est le taux estime ({ligne['taux_estime_pct']} %). "
                    "Sur des ventes reelles, plus irregulieres, la fourchette s'elargit et "
                    "la probabilite redevient nuancee."
                )

    # ===== C. Anomalies detectees =====
    st.subheader(f"Jours de vente anormaux - {categorie_choisie}")
    if anomalies is None:
        st.warning("Fichier data/anomalies.csv absent. Lance d'abord : python anomalies.py")
    else:
        anomalies_categorie = anomalies[anomalies["categorie"] == categorie_choisie]
        st.write(f"{len(anomalies_categorie)} anomalie(s) detectee(s) pour cette categorie.")
        st.dataframe(anomalies_categorie, width="stretch")

    # ===== D. Fiabilite du modele (validation retrospective / backtesting) =====
    # But : PROUVER que la prevision est credible. Le modele a ete entraine
    # uniquement sur 2024-2025 (validation_modele.py), puis on a compare ses
    # predictions aux VRAIES ventes de jan-juin 2026 (qu'il n'avait jamais vues).
    st.subheader(f"Fiabilite du modele - {categorie_choisie}")
    if validation is None:
        st.warning("Fichier data/validation_modele.csv absent. Lance d'abord : python validation_modele.py")
    else:
        validation_categorie = validation[validation["categorie"] == categorie_choisie].copy()
        validation_categorie["date"] = pd.to_datetime(validation_categorie["date"])

        # Indicateurs de qualite : MAE (erreur moyenne en ventes) et
        # MAPE (erreur moyenne en %). Fiabilite = 100 - MAPE.
        mae = validation_categorie["erreur_abs"].mean()
        mape = validation_categorie["erreur_pct"].mean()
        fiabilite = 100 - mape
        couleur_fiab = couleur_selon_taux(fiabilite)

        col_v1, col_v2, col_v3 = st.columns(3)
        col_v1.markdown(
            carte_kpi(
                "Erreur moyenne (MAE)",
                f"{mae:.0f}",
                "ventes / mois",
                couleur=GRIS,
                icone="ventes",
            ),
            unsafe_allow_html=True,
        )
        col_v2.markdown(
            carte_kpi(
                "Erreur moyenne (MAPE)",
                f"{mape:.1f} %",
                "ecart moyen entre prevu et reel",
                couleur=GRIS,
                icone="taux",
            ),
            unsafe_allow_html=True,
        )
        col_v3.markdown(
            carte_kpi(
                "Fiabilite estimee",
                f"{fiabilite:.1f} %",
                "100 - MAPE",
                couleur=couleur_fiab,
                extra_html=barres_signal(fiabilite, couleur_fiab),
                icone="objectif",
            ),
            unsafe_allow_html=True,
        )
        st.write("")

        # Graphique : ventes reelles vs ventes prevues sur la periode de test
        figure_validation = go.Figure()
        figure_validation.add_trace(
            go.Scatter(
                x=validation_categorie["date"], y=validation_categorie["ventes_reelles"],
                mode="lines+markers", line=dict(color=NUIT, width=2), name="Ventes reelles",
            )
        )
        figure_validation.add_trace(
            go.Scatter(
                x=validation_categorie["date"], y=validation_categorie["ventes_prevues"],
                mode="lines+markers", line=dict(color=BLEU, width=2, dash="dash"),
                name="Ventes prevues par le modele",
            )
        )
        figure_validation.update_layout(
            template="plotly_white", xaxis_title="Mois (test : jan-juin 2026)",
            yaxis_title="Quantite mensuelle",
        )
        st.plotly_chart(figure_validation, width="stretch")
        st.caption(
            "Test du modele : entraine uniquement sur 2024-2025, il predit jan-juin 2026 "
            "sans jamais avoir vu ces mois. On compare sa prevision (bleu pointille) aux "
            "vraies ventes (bleu nuit). Plus les deux courbes sont proches, plus le modele "
            "est fiable."
        )