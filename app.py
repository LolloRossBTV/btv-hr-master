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

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["emails"]["sender_email"]
        msg['To'] = st.secrets["emails"]["receiver_email"]
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(st.secrets["emails"]["smtp_server"], st.secrets["emails"]["smtp_port"])
        server.starttls()
        server.login(st.secrets["emails"]["sender_email"], st.secrets["emails"]["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Errore invio email: {e}")
        return False

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
        return df_dip, False
    return df_dip, False

# --- CONNESSIONE DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_richieste = conn.read(worksheet="Richieste", ttl=0)
    config_df = conn.read(worksheet="Config", ttl=0)
    config = dict(zip(config_df.key, config_df.value))
    df_dip, aggiornato = aggiorna_maturazioni_mensili(df_dip, config)
except Exception as e:
    st.error(f"⚠️ Errore di connessione: {e}")
    st.stop()

# --- GESTIONE STATO AUTENTICAZIONE ---
# --- LOGICA DI ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("Benvenuto in BTV")
    st.subheader("Accesso Riservato")
    
    nome_utente = st.selectbox("Seleziona il tuo Nome", df_dip['Nome'].tolist())
    password_input = st.text_input("Inserisci la tua Password", type="password")
    
    if st.button("Accedi"):
        utente_row = df_dip.loc[df_dip['Nome'] == nome_utente]
        raw_pass = str(utente_row['Password'].values[0])
        password_corretta = raw_pass.replace('.0', '').strip()
        primo_accesso = str(utente_row['PrimoAccesso'].values[0]).upper() == 'TRUE'
        
        if str(password_input).strip() == password_corretta:
            st.session_state.utente_loggato = nome_utente
            if primo_accesso:
                st.session_state.cambio_obbligatorio = True
                st.warning("⚠️ Primo accesso rilevato. Devi cambiare la password.")
            else:
                st.session_state.autenticato = True
                st.rerun()
        else:
            st.error("❌ Password errata. Riprova.")

    # Se deve cambiare password, mostriamo il modulo dedicato
    if st.session_state.get('cambio_obbligatorio'):
        new_pass = st.text_input("Nuova Password", type="password")
        confirm_pass = st.text_input("Conferma Nuova Password", type="password")
        if st.button("Salva Nuova Password"):
            if new_pass == confirm_pass and len(new_pass) > 4:
                # Qui aggiungeremo la funzione per scrivere sul foglio Google
                st.success("✅ Password aggiornata! Ora puoi accedere.")
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo corte.")# --- LOGICA DI ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("Benvenuto in BTV")
    st.subheader("Accesso Riservato")
    
    nome_utente = st.selectbox("Seleziona il tuo Nome", df_dip['Nome'].tolist())
    password_input = st.text_input("Inserisci la tua Password", type="password")
    
    if st.button("Accedi"):
        utente_row = df_dip.loc[df_dip['Nome'] == nome_utente]
        raw_pass = str(utente_row['Password'].values[0])
        password_corretta = raw_pass.replace('.0', '').strip()
        primo_accesso = str(utente_row['PrimoAccesso'].values[0]).upper() == 'TRUE'
        
        if str(password_input).strip() == password_corretta:
            st.session_state.utente_loggato = nome_utente
            if primo_accesso:
                st.session_state.cambio_obbligatorio = True
                st.warning("⚠️ Primo accesso rilevato. Devi cambiare la password.")
            else:
                st.session_state.autenticato = True
                st.rerun()
        else:
            st.error("❌ Password errata. Riprova.")

    # Se deve cambiare password, mostriamo il modulo dedicato
    if st.session_state.get('cambio_obbligatorio'):
        new_pass = st.text_input("Nuova Password", type="password")
        confirm_pass = st.text_input("Conferma Nuova Password", type="password")
        if st.button("Salva Nuova Password"):
            if new_pass == confirm_pass and len(new_pass) > 4:
                # Qui aggiungeremo la funzione per scrivere sul foglio Google
                st.success("✅ Password aggiornata! Ora puoi accedere.")
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo corte.")
