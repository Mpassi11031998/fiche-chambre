import streamlit as st
import pandas as pd
from fiche_chambre_fourreaux import traiter
from lecture_papier import images_du_xlsx, lire_fiche, type_image

st.set_page_config(page_title="Fiche de chambre – fourreaux", layout="wide")
st.title("Fiche de chambre : dessin des fourreaux")
st.caption("1) Déposez l'Excel brut  2) Lisez la fiche papier (automatique) ou saisissez-la  3) Vérifiez  4) Téléchargez la fiche traitée")

COLS = ["etat", "col", "ligne", "diametre"]
def df_vide():
    return pd.DataFrame({"etat": pd.Series(dtype="str"), "col": pd.Series(dtype="float"),
                         "ligne": pd.Series(dtype="float"), "diametre": pd.Series(dtype="float")})

if "v" not in st.session_state:   # version des widgets : change après chaque lecture auto
    st.session_state.v = 0
    st.session_state.donnees = {m: {"gs": 0.0, "diam": "", "df": df_vide()} for m in "ABCD"}
    st.session_state.infos = None

fichier = st.file_uploader("Fiche Excel brute (.xlsx)", type=["xlsx"])

# ---------------- Lecture automatique de la fiche papier ----------------
with st.expander("Lecture automatique de la fiche papier (facultatif)", expanded=fichier is not None):
    cle = st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, "secrets") else ""
    if not cle:
        cle = st.text_input("Clé API Anthropic (non enregistrée)", type="password")
    photo = None
    envoi = st.file_uploader("Photo de la fiche papier (JPEG/PNG)", type=["jpg", "jpeg", "png"], key="photo")
    if envoi:
        photo = envoi.getvalue()
    elif fichier is not None:
        imgs = [(n, b) for n, b in images_du_xlsx(fichier.getvalue()) if type_image(b)]
        if imgs:
            st.write("…ou choisissez la photo de la fiche papier parmi celles de l'Excel :")
            cols = st.columns(6)
            for i, (n, b) in enumerate(imgs):
                cols[i % 6].image(b, caption=f"n° {i+1}", use_container_width=True)
            choix = st.number_input("Numéro de l'image à lire (0 = aucune)", 0, len(imgs), 0)
            if choix:
                photo = imgs[choix - 1][1]
    if st.button("Lire la fiche papier", disabled=not (photo and cle)):
        with st.spinner("Lecture en cours…"):
            try:
                res = lire_fiche(photo, cle)
                for m in "ABCD":
                    d = res.get("masques", {}).get(m, {}) or {}
                    f = d.get("fourreaux", []) or []
                    st.session_state.donnees[m] = {
                        "gs": float(d.get("gs") or 0.0), "diam": d.get("diam_texte", "") or "",
                        "df": pd.DataFrame(f, columns=COLS).astype({"etat": "str"}) if f else df_vide()}
                st.session_state.infos = res
                st.session_state.v += 1
                st.rerun()
            except Exception as e:
                st.error(f"Lecture impossible : {e}")

infos = st.session_state.infos
if infos:
    st.info(f"Lecture terminée. Chambre : {infos.get('chambre','?')} – dimensions : {infos.get('dimensions','?')}"
            + (f" – remarque : {infos['remarque']}" if infos.get('remarque') else "")
            + ". **Vérifiez chaque masque ci-dessous avant de générer.**")
    for inc in infos.get("incertitudes", []) or []:
        st.warning(inc)

# ---------------- Saisie / vérification par masque ----------------
saisie = {"masques": {}}
v = st.session_state.v
onglets = st.tabs(["Masque A", "Masque B", "Masque C", "Masque D"])
for lettre, onglet in zip("ABCD", onglets):
    d = st.session_state.donnees[lettre]
    with onglet:
        c1, c2 = st.columns(2)
        gs = c1.number_input("Profondeur GS (m)", min_value=0.0, step=0.01, value=d["gs"], key=f"gs{lettre}{v}")
        diam = c2.text_input("Texte diamètre / matériau (ex. Ø100(TPC))", value=d["diam"], key=f"d{lettre}{v}")
        st.write("Un fourreau par ligne : `etat` = V ou pourcentage (20%, 65%…), `col` = position horizontale (0, 1, 2…), "
                 "`ligne` = rangée (0, 1…), `diametre` en mm.")
        df = st.data_editor(
            d["df"], num_rows="dynamic", key=f"t{lettre}{v}", use_container_width=True,
            column_config={
                "etat": st.column_config.TextColumn("État (V, 20%…)"),
                "col": st.column_config.NumberColumn("col", default=0, min_value=0, step=0.5),
                "ligne": st.column_config.NumberColumn("ligne", default=0, min_value=0, step=0.5),
                "diametre": st.column_config.NumberColumn("diamètre (mm)", default=100, min_value=10),
            })
        df = df.dropna(subset=["etat"])
        if len(df):
            saisie["masques"][lettre] = {
                "diam_texte": diam,
                "fourreaux": [{"etat": str(r.etat).strip(), "col": 0.0 if pd.isna(r.col) else float(r.col),
                               "ligne": 0.0 if pd.isna(r.ligne) else float(r.ligne),
                               "diametre": 100.0 if pd.isna(r.diametre) else float(r.diametre)}
                              for r in df.itertuples()]}
            if gs:
                saisie["masques"][lettre]["gs"] = gs

if st.button("Générer la fiche traitée", type="primary", disabled=fichier is None):
    try:
        sortie = traiter(fichier.getvalue(), saisie)
        nom = fichier.name.rsplit(".", 1)[0] + "_traitee.xlsx"
        st.success("Fiche générée.")
        st.download_button("Télécharger " + nom, sortie, file_name=nom,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.error(f"Erreur : {e}")
