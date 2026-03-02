import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE MATURAZIONI ---
MAT_FERIE_GUARDIA = 1.83
MAT_FERIE_FIDUCIARIO = 1.50
MAT_ROL_FIDUCIARIO = 0.50

# --- 2. INIZIALIZZAZIONE STATO ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 3. FUNZIONI LOGICHE ---
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

def aggiorna_maturazioni_mensili(df_dip, config, conn):
    oggi = datetime.now()
    try:
        last_upd_str = config.get('last_update', '2000-01-01')
        ultimo_aggiornamento = pd.to_datetime(last_upd_str)
        if oggi.month != ultimo_aggiornamento.month or oggi.year != ultimo_aggiornamento.year:
            st.info("🔄 Cambio mese rilevato. Aggiornamento saldi in corso...")
            df_dip = applica_maturazione(df_dip)
            # Aggiorna la data nel foglio Config (simulato qui come dizionario aggiornato)
            # In una versione reale, scriveresti sul foglio Config
            return df_dip, True
    except:
        return df_dip, False
    return df_dip, False

# --- 4. CONNESSIONE DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_richieste = conn.read(worksheet="Richieste", ttl=0)
    # Lettura configurazione per date aggiornamento
    config_df = conn.read(worksheet="Config", ttl=0)
    config = dict(zip(config_df.key, config_df.value))
    df_dip, aggiornato = aggiorna_maturazioni_mensili(df_dip, config, conn)
except Exception as e:
    st.error(f"⚠️ Errore di connessione: {e}")
    st.stop()

# --- 5. LOGICA DI ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("Benvenuto in BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Accesso Riservato")
        # --- CAMBIATO DA SELECTBOX A TEXT_INPUT ---
        st.info("Digita il tuo COGNOME NOME (es. ROSSINI LORENZO)")
        nome_digitato = st.text_input("Inserisci il tuo Nome e Cognome")
        password_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            n_pulito = nome_digitate.strip().upper()
            # Cerchiamo se il nome esiste nel database (senza badare a maiuscole/minuscole)
            if n_pulito in df_dip['Nome'].str.upper().values:
                idx_utente = df_dip[df_dip['Nome'].str.upper() == n_pulito].index[0]
                utente_row = df_dip.iloc[idx_utente]
                
                password_db = str(utente_row['Password']).replace('.0', '').strip()
                valore_primo_acc = str(utente_row['PrimoAccesso']).strip().upper()
                is_primo_accesso = valore_primo_acc in ['TRUE', 'SÌ', '1', 'VERO', '1.0']
                
                if str(password_input).strip() == password_db:
                    st.session_state.utente_loggato = utente_row['Nome']
                    if is_primo_accesso:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password errata.")
            else:
                st.error("❌ Nome utente non trovato nel sistema.")
