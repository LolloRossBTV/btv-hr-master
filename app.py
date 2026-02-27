import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAZIONE ---
MAT_FERIE_GUARDIA = 1.83
MAT_FERIE_FIDUCIARIO = 1.50
MAT_ROL_FIDUCIARIO = 0.50

def applica_maturazione(df_dip):
    df_dip['Ferie'] = pd.to_numeric(df_dip['Ferie'], errors='coerce').fillna(0)
    df_dip['ROL'] = pd.to_numeric(df_dip['ROL'], errors='coerce').fillna(0)
    for idx, row in df_dip.iterrows():
        if row['Contratto'] == "Guardia":
            df_dip.at[idx, 'Ferie'] += MAT_FERIE_GUARDIA
        else:
            df_dip.at[idx, 'Ferie'] += MAT_FERIE_FIDUCIARIO
            df_dip.at[idx, 'ROL'] += MAT_ROL_FIDUCIARIO
    return df_dip

def aggiorna_maturazioni_mensili(df_dip, config):
    oggi = datetime.now()
    try:
        last_upd_str = config.get('last_update', '2000-01-01')
        ultimo_aggiornamento = pd.to_datetime(last_upd_str)
        if oggi.month != ultimo_aggiornamento.month or oggi.year != ultimo_aggiornamento.year:
            st.info("🔄 Cambio mese rilevato. Aggiornamento saldi...")
            df_dip = applica_maturazione(df_dip)
            config['last_update'] = oggi.strftime('%Y-%m-%d')
            return df_dip, True
    except Exception as e:
        st.error(f"Errore aggiornamento: {e}")
    return df_dip, False

# --- LOGICA PRINCIPALE ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    config_df = conn.read(worksheet="Config", ttl=0)
    config = dict(zip(config_df.key, config_df.value))
    df_dip, aggiornato = aggiorna_maturazioni_mensili(df_dip, config)
except Exception as e:
    st.error(f"⚠️ ERRORE DI CONNESSIONE: {e}")
    st.stop()

st.title("Sistema Gestione Ferie BTV")
menu = ["Visualizza Saldi", "Inserisci Richiesta", "Gestione Admin"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Visualizza Saldi":
    st.subheader("Saldi Ferie e ROL")
    st.dataframe(df_dip)

elif choice == "Inserisci Richiesta":
    st.subheader("Nuova Richiesta")
    nome = st.selectbox("Seleziona Dipendente", df_dip['Nome'].tolist())
    tipo = st.radio("Tipo", ["Ferie", "ROL"])
    if st.button("Invia Richiesta"):
        st.success(f"Richiesta inviata per {nome}!")

elif choice == "Gestione Admin":
    st.subheader("Area Riservata")
    st.info("Qui potrai approvare le richieste.")
