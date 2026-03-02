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

# --- 3. FUNZIONE INVIO EMAIL ---
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

# --- 4. FUNZIONE MATURAZIONE MENSILE ---
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

# --- 5. CONNESSIONE DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    
    # Controllo Maturazione Mensile
    config_df = conn.read(worksheet="Config", ttl=0)
    config = dict(zip(config_df.key, config_df.value))
    oggi = datetime.now()
    ultimo_agg = pd.to_datetime(config.get('last_update', '2000-01-01'))
    
    if oggi.month != ultimo_agg.month or oggi.year != ultimo_agg.year:
        df_dip = applica_maturazione(df_dip)
        # Aggiornamento data nel foglio Config (richiede scrittura)
        st.info("🔄 Saldi aggiornati per il nuovo mese.")
except Exception as e:
    st.error(f"⚠️ Errore caricamento dati: {e}")
    st.stop()

# --- 6. LOGICA DI ACCESSO (LOGIN MANUALE) ---
if not st.session_state.autenticato:
    st.title("Benvenuto in BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Accesso Riservato")
        st.info("Digita COGNOME NOME (es. ROSSINI LORENZO)")
        nome_input = st.text_input("Inserisci il tuo Nome e Cognome")
        pass_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            n_pulito = nome_input.strip().upper()
            if n_pulito in df_dip['Nome'].str.upper().values:
                idx = df_dip[df_dip['Nome'].str.upper() == n_pulito].index[0]
                u_row = df_dip.iloc[idx]
                
                pass_db = str(u_row['Password']).replace('.0', '').strip()
                p_acc = str(u_row['PrimoAccesso']).strip().upper()
                
                if str(pass_input).strip() == pass_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    if p_acc in ['TRUE', 'SÌ', '1', 'VERO', '1.0']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password errata.")
            else:
                st.error("❌ Utente non trovato.")
    
    else:
        st.subheader("🔒 Cambio Password Obbligatorio")
        n_p = st.text_input("Nuova Password", type="password")
        c_p = st.text_input("Conferma Password", type="password")
        if st.button("Salva e Accedi"):
            if n_p == c_p and len(n_p) >= 5:
                idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato].tolist()[0]
                df_dip.at[idx, 'Password'] = n_p
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Errore password.")

else:
    # --- 7. INTERFACCIA UTENTE ---
    st.sidebar.success(f"Loggato: {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Nuova Richiesta", "Gestione Admin"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "I miei Saldi":
        st.header(f"Saldi di {st.session_state.utente_loggato}")
        dati_u = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati_u[['Ferie', 'ROL']])

    elif choice == "Nuova Richiesta":
        st.header("Compila la richiesta")
        with st.form("richiesta_ferie"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL", "Permesso"])
            dal = st.date_input("Dal")
            al = st.date_input("Al")
            note = st.text_area("Note")
            if st.form_submit_button("Invia"):
                testo = f"Dipendente: {st.session_state.utente_loggato}\nTipo: {tipo}\nPeriodo: {dal} - {al}\nNote: {note}"
                if send_email(f"Richiesta {tipo} - {st.session_state.utente_loggato}", testo):
                    st.success("✅ Richiesta inviata!")
                else:
                    st.error("❌ Errore invio email.")

    elif choice == "Gestione Admin":
        u_log = st.session_state.utente_loggato.upper()
        if "LORENZO" in u_log and "ROSSINI" in u_log:
            st.header("🛠️ Pannello Admin")
            st.dataframe(df_dip)
            st.divider()
            st.subheader("🔐 Reset Password")
            nome_res = st.text_input("Inserisci COGNOME NOME da resettare")
            if st.button("Esegui Reset"):
                n_p = nome_res.strip().upper()
                if n_p in df_dip['Nome'].str.upper().values:
                    idx = df_dip[df_dip['Nome'].str.upper() == n_p].index[0]
                    df_dip.at[idx, 'Password'] = '12345'
                    df_dip.at[idx, 'PrimoAccesso'] = 'TRUE'
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.success(f"Reset ok per {n_p}!")
                    st.balloons()
