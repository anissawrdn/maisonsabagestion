import requests
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime
import csv
import os
import re
import io
import altair as alt

st.set_page_config(page_title="Maison Saba - App de gestion", layout="wide")


# Navigation
modules = [
    "Dashboard",
    "Ventes",
    "Achats",
    "Stock & Inventaire",
    "Recettes",
    "RH",
    "Paie",
    "Trésorerie",
    "Comptes bancaires"
]

st.sidebar.title("Maison Saba Gestion")
module_actif = st.sidebar.radio("Aller à :", modules)
st.title(f"Module : {module_actif}")

# Fonction pour se connecter à Google Sheets
def get_public_google_sheet(sheet_id, range_name, api_key):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_name}?key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['values']
    else:
        st.error(f"Erreur {response.status_code}: {response.text}")
        return None


# Module Ventes
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
if module_actif == "Ventes":

    st.subheader("Enregistrement des ventes")
    ventes_file = "ventes.csv"
    plats_file = "plats.csv"

    if os.path.exists(plats_file):
        with open(plats_file, "r") as f:
            liste_plats = csv.load(f)
    else:
        liste_plats = {
            "Brioche perdue": 8.0,
            "Cookie pistache": 3.5
        }
    with st.expander("Gérer la liste des plats"):
        st.write("Plats disponibles :")
        for plat, prix in liste_plats.items():
            st.write(f"- {plat} : {prix} €") 
        col1, col2 = st.columns(2)
        with col1:
            new_plat = st.text_input("Ajouter un nouveau plat")
        with col2:
            new_prix = st.number_input("Prix (€)", min_value=0.0, step=0.5, key="new_prix") 

        if st.button("Ajouter à la liste"):
            if new_plat and new_plat not in liste_plats:
                liste_plats[new_plat] = new_prix
                with open(plats_file, "w") as f:
                    csv.dump(liste_plats, f)
                st.success(f"{new_plat} ajouté à la liste des plats.")

    if os.path.exists(ventes_file):
        df_ventes = pd.read_csv(ventes_file)
        df_ventes["Date"] = pd.to_datetime(df_ventes["Date"])
    else:
        df_ventes = pd.DataFrame(columns=["Date", "Produit", "Quantité", "Prix unitaire", "Total", "Mode de paiement"])

    # Dashboard Ventes
    st.markdown("---")
    st.subheader("Statistiques des ventes")
    if not df_ventes.empty:
        ventes_total = len(df_ventes)
        ca_total = df_ventes["Total"].sum()
        mois_actuel = datetime.date.today().month
        ventes_mois = df_ventes[df_ventes["Date"].dt.month == mois_actuel]
        nb_mois = len(ventes_mois)
        ca_mois = ventes_mois["Total"].sum()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Ventes totales", ventes_total)
        col2.metric("CA total (€)", f"{ca_total:.2f}")
        col3.metric("Ventes ce mois", nb_mois)
        col4.metric("CA ce mois (€)", f"{ca_mois:.2f}")
        st.markdown("### Répartition par mode de paiement")
        mode_totaux = df_ventes.groupby("Mode de paiement")["Total"].sum().sort_values(ascending=False)
        st.bar_chart(mode_totaux)
    else:
        st.info("Aucune vente enregistrée pour générer des statistiques.")
    st.markdown("---")
    st.subheader("Historique des ventes")

    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
        st.markdown("### Export")
        csv = df_ventes.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Télécharger l'historique (CSV)",
            data=csv,
            file_name='historique_ventes.csv',
            mime='text/csv'
        )
    else:
        st.info("Aucune vente enregistrée pour le moment.")
    # Saisie d'une nouvelle vente
    st.markdown("---")
    st.subheader("Ajouter une nouvelle vente")

    with st.form("ajout_vente"):
        col1, col2, col3 = st.columns(3)
    with col1:
            date_vente = st.date_input("Date", value=datetime.date.today())
    with col2:
            produit = st.selectbox("Produit vendu", list(liste_plats.keys()))
    with col3:
            quantite = st.number_input("Quantité", min_value=1, value=1)

    prix_defaut = liste_plats.get(produit, 0.0)
    prix_unitaire = st.number_input("Prix unitaire (€)", min_value=0.0, step=0.5, value=prix_defaut)
    mode_paiement = st.selectbox("Mode de paiement", ["Espèces", "Carte bancaire", "Ticket restaurant", "Autre"])
    total = quantite * prix_unitaire
    st.write(f"**Total : {total:.2f} €**")
    submit_vente = st.form_submit_button("Ajouter la vente")
    if submit_vente:
            nouvelle_vente = {
                "Date": str(date_vente),
                "Produit": produit,
                "Quantité": quantite,
                "Prix unitaire": prix_unitaire,
                "Total": total,
                "Mode de paiement": mode_paiement
            }
            df_ventes = pd.concat([df_ventes, pd.DataFrame([nouvelle_vente])], ignore_index=True)
            df_ventes.to_csv(ventes_file, index=False)
            st.success("Vente ajoutée avec succès !")
        
#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Module Achats
if module_actif == "Achats":
    st.subheader("Enregistrement des achats")
    achats_file = "achats.csv"
    if os.path.exists(achats_file):
        df_achats = pd.read_csv(achats_file)
        df_achats["Date"] = pd.to_datetime(df_achats["Date"], errors="coerce")
    else:
        df_achats = pd.DataFrame(columns=[
            "Date", "Fournisseur", "Produit", "Quantité", "Unité",
            "Prix unitaire", "Total", "Mode de paiement", "Catégorie"
        ])
    
    # Formulaire pour ajouter un achat
    with st.form("form_achat"):
        col1, col2, col3 = st.columns(3)
        with col1:
            date_achat = st.date_input("Date", value=datetime.date.today(), key="date_achat")
            fournisseur = st.text_input("Fournisseur", key="fournisseur")
        with col2:
            produit = st.text_input("Produit ou ingrédient", key="produit")
            quantite = st.number_input("Quantité", min_value=0.0, step=0.1, key="quantite")
        with col3:
            unite = st.text_input("Unité (g, kg, L...)", key="unite")
            prix_unitaire = st.number_input("Prix unitaire (€)", min_value=0.0, step=0.1, key="prix_unitaire")
        mode_paiement = st.selectbox("Mode de paiement", ["Carte bancaire", "Virement", "Chèque", "Espèces", "Autre"], key="mode_paiement")
        categorie = st.selectbox("Catégorie", ["Matières premières", "Emballages", "Boissons", "Décoration", "Autre"], key="categorie")
        total = quantite * prix_unitaire
        st.write(f"**Montant total : {total:.2f} €**")
        submit = st.form_submit_button("Ajouter l'achat")

    if submit:
        if not fournisseur or not produit or quantite == 0 or not unite ou prix_unitaire == 0:
            st.error("Tous les champs doivent être remplis pour ajouter un achat.")
        else:
            nouvel_achat = {
                "Date": str(date_achat),
                "Fournisseur": fournisseur,
                "Produit": produit,
                "Quantité": quantite,
                "Unité": unite,
                "Prix unitaire": prix_unitaire,
                "Total": total,
                "Mode de paiement": mode_paiement,
                "Catégorie": categorie
            }
            df_achats = pd.concat([df_achats, pd.DataFrame([nouvel_achat])], ignore_index=True)
            df_achats.to_csv(achats_file, index=False)
            st.success("Achat ajouté avec succès !")
    
    st.markdown("---")
    st.subheader("Historique des achats")

    if not df_achats.empty:
        df_achats["Date"] = pd.to_datetime(df_achats["Date"])
        total_achats = df_achats["Total"].sum()

        st.markdown(f"**Montant total des achats :** {total_achats:.2f} €")
        st.dataframe(df_achats, use_container_width=True)

        csv_export = df_achats.to_csv(index=False).encode('utf-8')
        st.download_button("Télécharger l'historique (CSV)", data=csv_export, file_name="achats_maison_saba.csv", mime="text/csv")

        # Vue par catégorie
        st.markdown("---")
        st.subheader("Vue par catégorie")
        total_par_categorie = df_achats.groupby("Catégorie")["Total"].sum().reset_index()

        # Create a bar chart with totals displayed on top of each bar using altair
        chart = alt.Chart(total_par_categorie).mark_bar(color='sandybrown').encode(
            x=alt.X('Catégorie', sort=None),
            y='Total',
            tooltip=['Catégorie', 'Total']
        ).properties(
            title='Total des achats par catégorie'
        ).mark_text(
            align='center',
            baseline='middle',
            dy=-10  # Nudges text up a bit so it doesn't overlap with the bar
        ).encode(
            text='Total:Q'
        )

        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucun achat enregistré pour le moment.")

    st.markdown("---")
    st.subheader("Modifier ou supprimer un achat")

    if not df_achats.empty:
        achat_selectionne = st.selectbox("Sélectionner un achat à modifier ou supprimer", df_achats.index, format_func=lambda x: f"{df_achats.at[x, 'Date']} - {df_achats.at[x, 'Produit']} - {df_achats.at[x, 'Fournisseur']}")

        achat = df_achats.loc[achat_selectionne]

        with st.form("modifier_supprimer_achat"):
            col1, col2, col3 = st.columns(3)
            with col1:
                date_achat = st.date_input("Date", value=achat["Date"], key="mod_date_achat")
                fournisseur = st.text_input("Fournisseur", value=achat["Fournisseur"], key="mod_fournisseur")
            with col2:
                produit = st.text_input("Produit ou ingrédient", value=achat["Produit"], key="mod_produit")
                quantite = st.number_input("Quantité", min_value=0.0, step=0.1, value=achat["Quantité"], key="mod_quantite")
            with col3:
                unite = st.text_input("Unité (g, kg, L...)", value=achat["Unité"], key="mod_unite")
                prix_unitaire = st.number_input("Prix unitaire (€)", min_value=0.0, step=0.1, value=achat["Prix unitaire"], key="mod_prix_unitaire")
            mode_paiement = st.selectbox("Mode de paiement", ["Carte bancaire", "Virement", "Chèque", "Espèces", "Autre"], index=["Carte bancaire", "Virement", "Chèque", "Espèces", "Autre"].index(achat["Mode de paiement"]), key="mod_mode_paiement")
            categorie = st.selectbox("Catégorie", ["Matières premières", "Emballages", "Boissons", "Décoration", "Autre"], index=["Matières premières", "Emballages", "Boissons", "Décoration", "Autre"].index(achat["Catégorie"]), key="mod_categorie")
            total = quantite * prix_unitaire
            st.write(f"**Montant total : {total:.2f} €**")
            submit_modification = st.form_submit_button("Modifier l'achat")
            submit_suppression = st.form_submit_button("Supprimer l'achat")

            if submit_modification:
                df_achats.at[achat_selectionne, "Date"] = str(date_achat)
                df_achats.at[achat_selectionne, "Fournisseur"] = fournisseur
                df_achats.at[achat_selectionne, "Produit"] = produit
                df_achats.at[achat_selectionne, "Quantité"] = quantite
                df_achats.at[achat_selectionne, "Unité"] = unite
                df_achats.at[achat_selectionne, "Prix unitaire"] = prix_unitaire
                df_achats.at[achat_selectionne, "Total"] = total
                df_achats.at[achat_selectionne, "Mode de paiement"] = mode_paiement
                df_achats.at[achat_selectionne, "Catégorie"] = categorie
                df_achats.to_csv(achats_file, index=False)
                st.success("Achat modifié avec succès !")               

            if submit_suppression:
                df_achats = df_achats.drop(achat_selectionne)
                df_achats.to_csv(achats_file, index=False)
                st.success("Achat supprimé avec succès !")
    else:
        st.info("Aucun achat enregistré pour le moment.")
#--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Module Stock & Inventaire
if module_actif == "Stock & Inventaire":
    ventes_file ="ventes.csv"
    if os.path.exists(ventes_file):
          df_ventes = pd.read_csv(ventes_file)
          df_ventes["Date"] = pd.to_datetime(df_ventes["Date"])
    else:
          df_ventes = pd.DataFrame(columns=["Date","Produit","Quantité","Prix unitaire","Total","Mode de paiement"])                                  
    stock_file = "stock.csv"
    if os.path.exists(stock_file):
        with open(stock_file, "r") as f:
            stock_data = csv.load(f)
    else:
        stock_data = {}
    st.subheader("Gestion du stock & inventaire")
    st.markdown("### Ajouter ou modifier un ingrédient")
    with st.form("ajout_stock"):
        col1, col2, col3 = st.columns(3)
        with col1:
            ingredient = st.text_input("Nom de l'ingrédient")
        with col2:
            quantite = st.number_input("Quantité disponible", min_value=0.0, step=0.1)
        with col3:
            seuil = st.number_input("Seuil d'alerte", min_value=0.0, step=0.1)
        submit_stock = st.form_submit_button("Enregistrer")
        if submit_stock and ingredient:
            stock_data[ingredient] = {"quantite": quantite, "seuil": seuil}
            with open(stock_file, "w") as f:
                csv.dump(stock_data, f)
            st.success("Stock mis à jour avec succès")
    st.markdown("---")
    st.subheader("Inventaire actuel")
    if stock_data:
        for nom, infos in stock_data.items():
            qte = infos.get("quantite", 0)
            seuil = infos.get("seuil", 0)
            if qte <= seuil:
                st.error(f"{nom} : {qte} (seuil {seuil}) — à réapprovisionner")
            else:
                st.write(f"{nom} : {qte} (seuil {seuil})")
    else:
        st.info("Aucun ingrédient enregistré.")
    st.markdown("---")
    st.subheader("Calculateur de recette")


    recette_file = "recettes.csv"
    if os.path.exists(recette_file):
        with open(recette_file, "r") as f:
            recettes = csv.load(f)
    else:
        recettes = {}
    if recettes:
        nom_recette = st.selectbox("Choisir une recette", list(recettes.keys()))
        nb_portions = st.number_input("Nombre de portions", min_value=1, value=1)
        st.markdown("### Ingrédients nécessaires")
        for ingr, qte in recettes[nom_recette]["ingredients"].items():
            total = qte * nb_portions
            st.write(f"{ingr} : {total}")

        mode_utilisation = st.radio("Action", ["Juste calculer", "Déduire du stock", "Créer une liste de courses"])
        if mode_utilisation == "Déduire du stock":
            for ingr, qte in recettes[nom_recette]["ingredients"].items():
                if ingr in stock_data:
                    stock_data[ingr]["quantite"] -= qte * nb_portions
            with open(stock_file, "w") as f:
                csv.dump(stock_data, f)
            st.success("Ingrédients déduits du stock.")
        else:
            st.info("Aucune recette enregistrée.")
 
# Module Recettes
if module_actif == "Recettes":
    st.subheader("Fiches de production des recettes")
    recette_file = "recettes.csv"
    if os.path.exists(recette_file):
        with open(recette_file, "r") as f:
            recettes = csv.load(f)
    else:
        recettes = {}

    st.markdown("### Ajouter une nouvelle recette")
    with st.form("ajout_recette"):
        nom = st.text_input("Nom de la recette")
        duree = st.text_input("Durée de conservation")
        ingredients = {}
        nb_ingredients = st.number_input("Nombre d'ingrédients", min_value=1, max_value=20, value=3)
        for i in range(nb_ingredients):
            col1, col2 = st.columns(2)
            with col1:
                ingr = st.text_input(f"Ingrédient {i+1}", key=f"ingr_{i}")
            with col2:
                qte = st.number_input(f"Quantité pour 1 portion", min_value=0.0, key=f"qte_{i}")
            if ingr:
                ingredients[ingr] = qte
 
        etapes = st.text_area("Étapes de préparation (utiles pour la formation)")
        submit_recette = st.form_submit_button("Ajouter la recette")
        if submit_recette and nom:
            recettes[nom] = {
                "duree": duree,
                "ingredients": ingredients,
                "etapes": etapes
            }
            with open(recette_file, "w") as f:
                csv.dump(recettes, f)
            st.success("Recette ajoutée avec succès !")
 
    st.markdown("---")
    st.subheader("Recettes existantes")
 
    if recettes:
        for nom, details in recettes.items():
            with st.expander(nom):
                st.markdown(f"**Durée de conservation** : {details.get('duree', '')}")
                st.markdown("**Ingrédients pour 1 portion :**")
                for ingr, qte in details["ingredients"].items():
                    st.write(f"- {ingr} : {qte}")
                st.markdown("**Étapes :**")
                st.write(details["etapes"])
    else:
        st.info("Aucune recette enregistrée pour le moment.")
 
# Module RH
if module_actif == "RH":
    st.subheader("Gestion des ressources humaines")
    employes_file = "employes.csv"
    planning_file = "planning.csv"
 
    if os.path.exists(employes_file):
        with open(employes_file, "r") as f:
            employes = csv.load(f)
    else:
        employes = {}
 
    if os.path.exists(planning_file):
        with open(planning_file, "r") as f:
            planning = csv.load(f)
    else:
        planning = {}
 
    st.markdown("### Fiche employé")
    for nom in employes:
        with st.expander(nom):
            st.write(f"**Contrat :** {employes[nom].get('contrat', 'Non précisé')}")
            st.write(f"**Heures travaillées ce mois** : {employes[nom].get('heures_mois', 0)}h")
            st.write(f"**Heures cette semaine** : {employes[nom].get('heures_semaine', 0)}h")
            st.write(f"**Pointage :** {employes[nom].get('pointage', '')}")
 
    st.markdown("---")
    st.subheader("Planning de l'équipe")
 
    jours_semaine = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
 
    planning_saisi = {}
    with st.form("form_planning"):
        for jour in jours_semaine:
            st.markdown(f"**{jour}**")
            for nom in employes:
                plage = st.text_input(f"{nom} ({jour})", value=planning.get(jour, {}).get(nom, ""), key=f"{jour}_{nom}")
                if jour not in planning_saisi:
                    planning_saisi[jour] = {}
                planning_saisi[jour][nom] = plage
 
        submit_planning = st.form_submit_button("Enregistrer le planning")
        if submit_planning:
            planning.update(planning_saisi)
            with open(planning_file, "w") as f:
                csv.dump(planning, f)
            st.success("Planning enregistré avec succès")
 
    st.markdown("### Calendrier des absences")
    for nom in employes:
        st.write(f"{nom} : {employes[nom].get('absences', 'Aucune absence renseignée')}")
 
# Module Paie
if module_actif == "Paie":
    st.subheader("Tableau de paie mensuel")
 
    employes_file = "employes.csv"
    if os.path.exists(employes_file):
        with open(employes_file, "r") as f:
            employes = csv.load(f)
    else:
        employes = {}
 
    st.markdown("### Paramètres généraux")
    taux_horaire_base = st.number_input("Taux horaire (€)", min_value=0.0, step=0.5, value=12.0)
    taux_h_sup = st.number_input("Taux heure supp (€)", min_value=0.0, step=0.5, value=18.0)
 
    paie_data = []
    for nom in employes:
        heures = employes[nom].get("heures_mois", 0)
        supp = employes[nom].get("heures_supp", 0)
        prime = employes[nom].get("prime", 0)
        brut = heures * taux_horaire_base + supp * taux_h_sup + prime
        cotisation = brut * 0.22  # à adapter
        net = brut - cotisation
        paie_data.append({
            "Employé": nom,
            "Heures": heures,
            "HS": supp,
            "Taux h": taux_horaire_base,
            "Taux HS": taux_h_sup,
            "Brut": brut,
            "Prime": prime,
            "Cotisation": cotisation,
            "Net à payer": net
        })
    df_paie = pd.DataFrame(paie_data)
    st.dataframe(df_paie, use_container_width=True)

# Module Trésorerie
if module_actif == "Trésorerie":
    st.subheader("Vue d’ensemble de la trésorerie")
   
    ventes_file = "ventes.csv"
    achats_file = "achats.csv"
    treso_file = "tresorerie.csv"

    if os.path.exists(treso_file):
        df_treso = pd.read_csv(treso_file)
        df_treso["Date"] = pd.to_datetime(df_treso["Date"])
    else:
        df_treso = pd.DataFrame(columns=["Date", "Libellé", "Type", "Montant", "Mode", "Catégorie"])

    # Synchronisation avec ventes et achats si besoin (optionnel ici, tu les gères manuellement)

    # Vue globale
    st.markdown("### Bilan global")
   
    total_entrees = df_treso[df_treso["Type"] == "Entrée"]["Montant"].sum()
    total_sorties = df_treso[df_treso["Type"] == "Sortie"]["Montant"].sum()
    solde = total_entrees - total_sorties
    col1, col2, col3 = st.columns(3)
    col1.metric("Entrées (€)", f"{total_entrees:.2f}")
    col2.metric("Sorties (€)", f"{total_sorties:.2f}")
    col3.metric("Solde actuel (€)", f"{solde:.2f}")

    df_treso["Mois"] = df_treso["Date"].apply(lambda x: x.strftime("%Y-%m"))
    graph_data = df_treso.groupby(["Mois", "Type"])["Montant"].sum().unstack(fill_value=0)
    st.bar_chart(graph_data)

    st.markdown("---")
    st.subheader("Ajouter un mouvement manuel")
    with st.form("form_treso"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date du mouvement", value=datetime.date.today())
            libelle = st.text_input("Libellé")
            montant = st.number_input("Montant (€)", min_value=0.0, step=0.5)
        with col2:
            type_mvt = st.selectbox("Type", ["Entrée", "Sortie"])
            mode = st.selectbox("Mode de paiement", ["Espèces", "Carte bancaire", "Virement", "Chèque", "Autre"])
            categorie = st.selectbox("Catégorie", ["Divers", "Personnel", "Vente", "Achat", "Autre"])
        submit_treso = st.form_submit_button("Ajouter le mouvement")
        if submit_treso:
            ajout = {
                "Date": pd.to_datetime(date),
                "Libellé": libelle,
                "Type": type_mvt,
                "Montant": montant,
                "Mode": mode,
                "Catégorie": categorie
            }
            df_treso = pd.concat([df_treso, pd.DataFrame([ajout])], ignore_index=True)
            df_treso.to_csv(treso_file, index=False)
            st.success("Mouvement ajouté avec succès !")
 
    st.markdown("---")
    st.subheader("Historique des mouvements")
 
    if not df_treso.empty:
        df_treso = df_treso.sort_values("Date", ascending=False)
        st.dataframe(df_treso, use_container_width=True)
        csv = df_treso.to_csv(index=False).encode('utf-8')
        st.download_button("Télécharger l'historique (CSV)", data=csv, file_name="tresorerie_maison_saba.csv", mime="text/csv")
    else:
        st.info("Aucun mouvement de trésorerie enregistré.")
 
# Module Comptes bancaires
if module_actif == "Comptes bancaires":
    st.subheader("Suivi des comptes bancaires")
    comptes_file = "comptes_bancaires.csv"
 
    if os.path.exists(comptes_file):
        with open(comptes_file, "r") as f:
            comptes_data = csv.load(f)
    else:
        comptes_data = {}
 
    with st.form("ajout_compte"):
        col1, col2 = st.columns(2)
        with col1:
            compte_nom = st.text_input("Nom du compte", key="compte_nom")
        with col2:
            mois = st.selectbox(
                "Mois",
                ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"],
                index=datetime.date.today().month - 1
            )
        solde = st.number_input("Solde à la fin du mois (€)", step=0.01)
        submit_solde = st.form_submit_button("Enregistrer le solde")

        if submit_solde and compte_nom:
            if compte_nom not in comptes_data:
                comptes_data[compte_nom] = {}
            comptes_data[compte_nom][mois] = solde
            with open(comptes_file, "w") as f:
                csv.dump(comptes_data, f)
            st.success("Solde enregistré avec succès")

    if comptes_data:
        st.markdown("---")
        st.subheader("Soldes enregistrés")
        for compte, mois_data in comptes_data.items():
            st.markdown(f"**{compte}**")
            df_solde = pd.DataFrame(list(mois_data.items()), columns=["Mois", "Solde (€)"]).sort_values("Mois")
            st.dataframe(df_solde, use_container_width=True)
    else:
        st.info("Aucun compte enregistré pour le moment.")
