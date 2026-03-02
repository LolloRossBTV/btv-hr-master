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
        nome_utente = st.selectbox("Seleziona il tuo Nome", df_dip['Nome'].tolist())
        password_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            utente_row = df_dip.loc[df_dip['Nome'] == nome_utente]
            password_db = str(utente_row.iloc[0]['Password']).replace('.0', '').strip()
            valore_primo_acc = str(utente_row.iloc[0]['PrimoAccesso']).strip().upper()
            is_primo_accesso = valore_primo_acc in ['TRUE', 'SÌ', '1', 'VERO', '1.0']
            
            if str(password_input).strip() == password_db:
                st.session_state.utente_loggato = nome_utente
                if is_primo_accesso:
                    st.session_state.cambio_obbligatorio = True
                    st.rerun()
                else:
                    st.session_state.autenticato = True
                    st.rerun()
            else:
                st.error("❌ Password errata.")
    
    else:
        st.subheader("🔒 Cambio Password Obbligatorio")
        st.info(f"Ciao {st.session_state.utente_loggato}, imposta una nuova password.")
        new_pass = st.text_input("Nuova Password", type="password")
        confirm_pass = st.text_input("Conferma Nuova Password", type="password")
        
        if st.button("Salva e Accedi"):
            if new_pass == confirm_pass and len(new_pass) >= 5:
                idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato].tolist()[0]
                df_dip.at[idx, 'Password'] = new_pass
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.success("✅ Password aggiornata!")
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password non valide (min 5 car).")

else:
    # --- 6. INTERFACCIA UTENTI LOGGATI ---
    st.sidebar.success(f"Loggato: {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Nuova Richiesta", "Gestione Admin"]
    choice = st.sidebar.selectbox("Cosa vuoi fare?", menu)

    if choice == "I miei Saldi":
        st.header(f"Saldi di {st.session_state.utente_loggato}")
        dati_u = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati_u[['Ferie', 'ROL']])

    elif choice == "Nuova Richiesta":
        st.header("Compila la richiesta")
        with st.form("form_richiesta"):
            tipo = st.radio("Tipo", ["Ferie", "ROL", "Permesso"])
            inizio = st.date_input("Inizio")
            fine = st.date_input("Fine")
            note = st.text_area("Note aggiuntive")
            submit = st.form_submit_button("Invia Richiesta")
            
            if submit:
                messaggio = f"Nuova richiesta da {st.session_state.utente_loggato}:\nTipo: {tipo}\nDal: {inizio}\nAl: {fine}\nNote: {note}"
                if send_email(f"Richiesta {tipo} - {st.session_state.utente_loggato}", messaggio):
                    st.success("✅ Richiesta inviata via e-mail!")
                else:
                    st.warning("⚠️ Errore invio e-mail, avvisa l'amministratore.")

    elif choice == "Gestione Admin":
        u_log = st.session_state.utente_loggato.upper()
        if "LORENZO" in u_log and "ROSSINI" in u_log:
            st.header("🛠️ Pannello Admin")
            st.subheader("Riepilogo Dipendenti")
            st.dataframe(df_dip)
            
            st.divider()
            st.subheader("🔐 Reset Password")
            st.warning("⚠️ Inserire il nome esattamente come nel database.")
            
            nome_da_resettare = st.text_input("Inserisci COGNOME NOME della risorsa")
            
            if st.button("Esegui Reset a 12345"):
                n_pulito = nome_da_resettare.strip().upper()
                if n_pulito in df_dip['Nome'].str.upper().values:
                    idx = df_dip[df_dip['Nome'].str.upper() == n_pulito].index[0]
                    df_dip.at[idx, 'Password'] = '12345'
                    df_dip.at[idx, 'PrimoAccesso'] = 'TRUE'
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.success
