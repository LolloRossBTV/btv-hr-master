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

# --- LOGICA DI ACCESSO (LOGIN) ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False

if not st.session_state.autenticato:
    st.sidebar.image("https://www.gstatic.com/images/branding/product/2x/avatar_anonymous_128dp.png", width=100)
    st.title("Benvenuto in BTV")
    st.subheader("Accesso Riservato")
    
    nome_utente = st.selectbox("Seleziona il tuo Nome", df_dip['Nome'].tolist())
    # Assicurati che nel foglio Google ci sia la colonna 'Password'
    password_input = st.text_input("Inserisci la tua Password", type="password")
    
    if st.button("Accedi"):
        password_corretta = df_dip.loc[df_dip['Nome'] == nome_utente, 'Password'].values[0]
        if str(password_input) == str(password_corretta):
            st.session_state.autenticato = True
            st.session_state.utente_loggato = nome_utente
            st.rerun()
        else:
            st.error("❌ Password errata. Riprova.")
else:
    # --- INTERFACCIA PER UTENTI LOGGATI ---
    st.sidebar.success(f"Loggato come: {st.session_state.utente_loggato}")
    if st.sidebar.button("Log-out"):
        st.session_state.autenticato = False
        st.rerun()

    st.title("Sistema Gestione Ferie BTV")
    menu = ["I miei Saldi", "Inserisci Richiesta", "Gestione Admin"]
    choice = st.sidebar.selectbox("Cosa vuoi fare?", menu)

    # Filtra i dati per mostrare solo quelli dell'utente loggato
    dati_utente = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]

    if choice == "I miei Saldi":
        st.subheader(f"Situazione di {st.session_state.utente_loggato}")
        st.table(dati_utente[['Ferie', 'ROL']])

    elif choice == "Inserisci Richiesta":
        st.subheader("Nuova Richiesta")
        with st.form("form_richiesta"):
            tipo = st.radio("Tipo", ["Ferie", "ROL", "Permesso"])
            inizio = st.date_input("Dal")
            fine = st.date_input("Al")
            note = st.text_area("Note aggiuntive")
            submit = st.form_submit_button("Invia Richiesta")
            
            if submit:
                messaggio = f"Nuova richiesta da {st.session_state.utente_loggato}: {tipo} dal {inizio} al {fine}\nNote: {note}"
                if send_email(f"Richiesta {tipo} - {st.session_state.utente_loggato}", messaggio):
                    st.success("✅ Richiesta inviata via e-mail!")
                else:
                    st.warning("⚠️ Errore nell'invio e-mail, avvisa l'amministratore.")

    elif choice == "Gestione Admin":
        # Qui potrai aggiungere un controllo: se l'utente è Lorenzo, mostra tutto
        if st.session_state.utente_loggato == "Lorenzo Rossini": # Cambia con il tuo nome esatto sul foglio
            st.subheader("Area Amministrazione")
            st.write("Tutti i dipendenti:")
            st.dataframe(df_dip)
        else:
            st.error("Area riservata all'amministratore.")
    st.subheader("Area Riservata Amministrazione")
    st.write("Richieste Ricevute:")
    st.dataframe(df_richieste)
