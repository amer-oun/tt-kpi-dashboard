import base64
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Logique de calcul KPI partagee avec calcul_kpi.py (voir kpi.py)
from kpi import preparer_ventes, calculer_kpi

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


def charger_si_existe(chemin):
    """Charge un CSV s'il existe, sinon renvoie None.
    Pour les fichiers produits aux etapes 6 et 7 : si les scripts n'ont pas
    ete lances, on affiche un message plutot qu'une erreur."""
    if os.path.exists(chemin):
        return pd.read_csv(chemin)
    return None


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


def carte_kpi(titre, valeur, sous_texte="", couleur=BLEU, extra_html="", icone="", delai=0):
    """Fabrique une carte KPI HTML (chiffre en Fira Code facon telemetrie).

    - icone : nom d'une icone SVG (voir ICONES) affichee en haut a droite ;
    - delai : decalage d'apparition (en secondes) pour l'effet de cascade.
    """
    return f"""
    <div class="tt-card" style="border-top: 3px solid {couleur}; animation-delay: {delai}s;">
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
st.set_page_config(
    page_title="TT - Console de performance commerciale",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
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

    /* ---------- Bandeau d'en-tete (masthead) ---------- */
    .tt-masthead {{
        position: relative; overflow: hidden;
        background:
            radial-gradient(circle at 92% -30%, rgba(0,114,188,.45), transparent 45%),
            linear-gradient(120deg, var(--tt-nuit) 0%, #0E3A63 100%);
        border-radius: 16px; padding: 24px 30px 28px 30px; margin-bottom: 22px;
        box-shadow: 0 8px 24px rgba(10,42,74,.20);
        animation: apparition .5s ease both;
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
    .tt-masthead .tt-title {{ color: #ffffff !important; margin: 0; font-size: 30px;
             font-weight: 700; letter-spacing: -0.5px; }}
    .tt-masthead .tt-sub   {{ color: #9fc4e6 !important; margin: 6px 0 0 0; font-size: 14px;
             letter-spacing: .3px; }}
    .tt-logo-img {{ height: 62px; width: auto; background: #fff; padding: 8px 12px;
             border-radius: 12px; display: block; box-shadow: 0 2px 8px rgba(0,0,0,.12); }}

    /* ---------- Cartes KPI (style data-dense + survol) ---------- */
    .tt-card {{
        background: var(--tt-surface); border: 1px solid var(--tt-bordure); border-radius: 14px;
        padding: 15px 18px 16px 18px; box-shadow: 0 2px 8px rgba(10,42,74,.05);
        animation: apparition .5s ease both;
        transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
    }}
    .tt-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 10px 22px rgba(10,42,74,.12);
        border-color: #C3D4E8;
    }}
    .tt-card-entete {{ display: flex; align-items: center; justify-content: space-between; }}
    .tt-card-icone {{ opacity: .85; flex-shrink: 0; }}
    .tt-card-titre {{ color: var(--tt-muet); font-size: 12px; font-weight: 600;
                     text-transform: uppercase; letter-spacing: .8px; }}
    .tt-card-valeur {{
        color: var(--tt-nuit); font-family: var(--mono);
        font-size: 31px; font-weight: 600; font-variant-numeric: tabular-nums;
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
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- Bandeau d'en-tete ----
st.markdown(
    f"""
    <div class="tt-masthead">
        <div class="tt-brand">
            {logo_html()}
        </div>
        <h1 class="tt-title">Console de performance commerciale</h1>
        <p class="tt-sub">Suivi des ventes, prevision et alertes &middot; objectifs mensuels et annuels</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
#  Chargement et calcul des KPI (meme logique que calcul_kpi.py)
# ============================================================================
ventes = pd.read_csv("data/ventes.csv")
objectifs = pd.read_csv("data/objectifs.csv")

prevision = charger_si_existe("data/prevision.csv")
atteinte = charger_si_existe("data/atteinte_objectif.csv")
anomalies = charger_si_existe("data/anomalies.csv")

# Preparation des ventes (dates + annee/mois) et calcul des KPI,
# via le module partage kpi.py (meme logique que calcul_kpi.py).
ventes = preparer_ventes(ventes)
kpi = calculer_kpi(ventes, objectifs)

# ============================================================================
#  Selecteurs (barre laterale)
# ============================================================================
st.sidebar.header("Filtres")
categories = kpi["categorie"].unique()
categorie_choisie = st.sidebar.selectbox("Categorie", categories)

annees_disponibles = kpi.loc[kpi["categorie"] == categorie_choisie, "annee"].unique()
annee_choisie = st.sidebar.selectbox("Annee", sorted(annees_disponibles))

kpi_filtre = kpi[(kpi["categorie"] == categorie_choisie) & (kpi["annee"] == annee_choisie)]
kpi_annee = kpi[kpi["annee"] == annee_choisie]

# ============================================================================
#  Cartes KPI (le taux porte la signature "barres de signal")
# ============================================================================
total_realise = kpi_filtre["ventes_reelles"].sum()
total_objectif = kpi_filtre["objectif_mensuel"].sum()
taux_global = round(total_realise / total_objectif * 100, 1) if total_objectif != 0 else None
ecart_global = total_realise - total_objectif
couleur_taux = couleur_selon_taux(taux_global)

colonne_1, colonne_2, colonne_3 = st.columns(3)
# delai croissant -> les cartes apparaissent en cascade (effet "stagger")
colonne_1.markdown(
    carte_kpi(
        "Ventes realisees (cumul)",
        f"{total_realise:,}".replace(",", " "),
        f"{categorie_choisie} - {annee_choisie}",
        icone="ventes",
        delai=0.00,
    ),
    unsafe_allow_html=True,
)
colonne_2.markdown(
    carte_kpi(
        "Objectif (cumul)",
        f"{total_objectif:,}".replace(",", " "),
        "cible sur la periode",
        couleur=GRIS,
        icone="objectif",
        delai=0.08,
    ),
    unsafe_allow_html=True,
)
colonne_3.markdown(
    carte_kpi(
        "Taux de realisation",
        f"{taux_global} %" if taux_global is not None else "N/A",
        f"ecart : {ecart_global:+} ventes" if taux_global is not None else "",
        couleur=couleur_taux,
        extra_html=barres_signal(taux_global, couleur_taux),
        icone="taux",
        delai=0.16,
    ),
    unsafe_allow_html=True,
)

st.write("")

st.download_button(
    label="Telecharger le KPI filtre (CSV)",
    data=kpi_filtre.to_csv(index=False).encode("utf-8"),
    file_name=f"kpi_{categorie_choisie}_{annee_choisie}.csv",
    mime="text/csv",
)

# ============================================================================
#  Bandeau d'alertes automatiques (toutes categories, annee selectionnee)
# ============================================================================
# But : rendre le dashboard "actionnable". Le responsable voit tout de suite
# quelles categories sont en retard sur leur objectif, sans lire les chiffres.
st.subheader(f"Alertes - situation cumulee {annee_choisie}")

# On cumule ventes et objectifs de l'annee, par categorie
alertes = (
    kpi_annee.groupby("categorie")[["ventes_reelles", "objectif_mensuel"]]
    .sum()
    .reset_index()
)
# Taux cumule, avec protection contre la division par zero
alertes["taux"] = alertes.apply(
    lambda r: round(r["ventes_reelles"] / r["objectif_mensuel"] * 100, 1)
    if r["objectif_mensuel"] else None,
    axis=1,
)

for _, ligne_alerte in alertes.iterrows():
    manque = int(ligne_alerte["objectif_mensuel"] - ligne_alerte["ventes_reelles"])
    taux = ligne_alerte["taux"]
    nom = ligne_alerte["categorie"]
    if taux is None:
        st.info(f"{nom} : pas d'objectif defini.")
    elif taux >= 100:
        # st.success = message vert (avec icone integree)
        st.success(f"{nom} : objectif atteint a ce stade ({taux} %).")
    elif taux >= 90:
        # st.warning = message orange
        st.warning(f"{nom} : proche de l'objectif ({taux} %) - il manque {manque} ventes.")
    else:
        # st.error = message rouge
        st.error(f"{nom} : en retard ({taux} %) - il manque {manque} ventes.")

# --- Bouton d'export du rapport PDF ---
# On genere le PDF a la demande et on le propose au telechargement.
rapport_pdf = generer_rapport_pdf(
    categorie_choisie, annee_choisie, total_realise, total_objectif,
    taux_global, ecart_global, alertes,
)
st.download_button(
    label="Telecharger le rapport PDF",
    data=rapport_pdf,
    file_name=f"rapport_{categorie_choisie}_{annee_choisie}.pdf",
    mime="application/pdf",
)

# ============================================================================
#  Onglets
# ============================================================================
onglet_tableau, onglet_cumule, onglet_sous_categories, onglet_comparaison, onglet_regions, onglet_prevision = st.tabs(
    [
        "Tableau & mensuel",
        "Suivi cumule",
        "Detail sous-categories",
        "Comparaison categories",
        "Analyse regionale",
        "Prevision & alertes",
    ]
)

# --- Onglet 1 : tableau KPI + histogramme mensuel ---
with onglet_tableau:
    st.subheader(f"Tableau KPI - {categorie_choisie} {annee_choisie}")
    st.dataframe(kpi_filtre, use_container_width=True)

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
    st.plotly_chart(figure, use_container_width=True)

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
    st.plotly_chart(figure_jours, use_container_width=True)

# --- Onglet 2 : suivi cumule ---
with onglet_cumule:
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
    st.plotly_chart(figure_cumule, use_container_width=True)

# --- Onglet 3 : detail par sous-categorie ---
with onglet_sous_categories:
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
    st.plotly_chart(figure_sous_categorie, use_container_width=True)

# --- Onglet 4 : comparaison des categories ---
with onglet_comparaison:
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
    st.plotly_chart(figure_comparaison, use_container_width=True)

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
    st.plotly_chart(figure_taux_comparaison, use_container_width=True)

# --- Onglet 5 : analyse regionale ---
with onglet_regions:
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
                delai=0.08,
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
    st.plotly_chart(figure_region, use_container_width=True)

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
    st.plotly_chart(figure_region_mois, use_container_width=True)

    st.caption(
        "Note : la dimension regionale est simulee (ajoutee via ajouter_region.py) "
        "pour demontrer la capacite d'analyse geographique."
    )

# --- Onglet 6 : prevision + probabilite d'atteinte + anomalies ---
with onglet_prevision:

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
        st.plotly_chart(figure_prevision, use_container_width=True)
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
                    delai=0.00,
                ),
                unsafe_allow_html=True,
            )
            col2.markdown(
                carte_kpi(
                    "Objectif annuel",
                    f"{int(ligne['objectif_annuel']):,}".replace(",", " "),
                    couleur=GRIS,
                    icone="objectif",
                    delai=0.08,
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
                    delai=0.16,
                ),
                unsafe_allow_html=True,
            )
            st.write("")
            # Jauge visuelle du taux d'atteinte annuel (compteur)
            st.plotly_chart(
                jauge_taux(ligne["taux_estime_pct"], f"Taux d'atteinte estime - {int(ligne['annee'])}"),
                use_container_width=True,
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

    # ===== C. Anomalies detectees =====
    st.subheader(f"Jours de vente anormaux - {categorie_choisie}")
    if anomalies is None:
        st.warning("Fichier data/anomalies.csv absent. Lance d'abord : python anomalies.py")
    else:
        anomalies_categorie = anomalies[anomalies["categorie"] == categorie_choisie]
        st.write(f"{len(anomalies_categorie)} anomalie(s) detectee(s) pour cette categorie.")
        st.dataframe(anomalies_categorie, use_container_width=True)