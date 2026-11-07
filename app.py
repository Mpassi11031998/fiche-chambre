import streamlit as st
import pandas as pd
from fiche_chambre_fourreaux import traiter

st.set_page_config(page_title="Fiche de chambre – fourreaux", layout="wide")
st.title("Fiche de chambre : dessin des fourreaux")
st.caption("1) Déposez l'Excel brut  2) Saisissez les fourreaux de la fiche papier  3) Téléchargez la fiche traitée")

fichier = st.file_uploader("Fiche Excel brute (.xlsx)", type=["xlsx"])

ETATS = ["V", "10%", "20%", "30%", "40%", "50%", "65%", "80%", "100%"]
saisie = {"masques": {}}
vide = pd.DataFrame({"etat": ["V"], "col": [0], "ligne": [0], "diametre": [100]})

onglets = st.tabs(["Masque A", "Masque B", "Masque C", "Masque D"])
for lettre, onglet in zip("ABCD", onglets):
    with onglet:
        c1, c2 = st.columns(2)
        gs = c1.number_input("Profondeur GS (m)", min_value=0.0, step=0.01, key=f"gs{lettre}")
        diam = c2.text_input("Texte diamètre / matériau (ex. Ø100(TPC))", key=f"d{lettre}")
        st.write("Un fourreau par ligne. `col` = position horizontale (0, 1, 2…), `ligne` = rangée (0, 1…), `diametre` en mm.")
        df = st.data_editor(
            vide, num_rows="dynamic", key=f"t{lettre}", use_container_width=True,
            column_config={"etat": st.column_config.SelectboxColumn("État", options=ETATS)},
        )
        df = df.dropna(subset=["etat"])
        if len(df) and (gs or diam or df["etat"].notna().any()):
            saisie["masques"][lettre] = {
                "gs": gs if gs else None,
                "diam_texte": diam,
                "fourreaux": [
                    {"etat": str(r.etat), "col": float(r.col), "ligne": float(r.ligne), "diametre": float(r.diametre)}
                    for r in df.itertuples()
                ],
            }
            if not gs:
                del saisie["masques"][lettre]["gs"]

if st.button("Générer la fiche traitée", type="primary", disabled=fichier is None):
    try:
        sortie = traiter(fichier.getvalue(), saisie)
        nom = fichier.name.rsplit(".", 1)[0] + "_traitee.xlsx"
        st.success("Fiche générée.")
        st.download_button("Télécharger " + nom, sortie, file_name=nom,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.error(f"Erreur : {e}")
