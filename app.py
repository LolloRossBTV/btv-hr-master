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

# Inizializzazione variabili di stato (Risolve l'errore riga 71)
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

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
        st.error(f"Errore email: {e}")
        return False

# --- CONNESSIONE DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_richieste = conn.read(worksheet="Richieste", ttl=0)
except Exception as e:
    st.error(f"⚠️ Errore di connessione: {e}")
    st.stop()

# --- LOGICA DI ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("Benvenuto in BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Accesso Riservato")
        nome_utente = st.selectbox("Seleziona il tuo Nome", df_dip['Nome'].tolist())
        password_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            utente_row = df_dip.loc[df_dip['Nome'] == nome_utente]
            # Usiamo la colonna E (indice 4) per la password
            password_corretta = str(utente_row.iloc[0]['Password']).replace('.0', '').strip()
            # Usiamo la colonna F (indice 5) per il primo accesso
            primo_acc = str(utente_row.iloc[0]['PrimoAccesso']).upper()
            
            if str(password_input).strip() == password_corretta:
                st.session_state.utente_loggato = nome_utente
                if primo_acc == 'TRUE' or primo_acc == '1':
                    st.session_state.cambio_obbligatorio = True
                    st.rerun()
                else:
                    st.session_state.autenticato = True
                    st.rerun()
            else:
                st.error("❌ Password errata.")
    
    else:
        st.subheader("🔒 Cambio Password Obbligatorio")
        new_pass = st.text_input("Nuova Password", type="password")
        confirm_pass = st.text_input("Conferma Password", type="password")
        
        if st.button("Salva e Accedi"):
            if new_pass == confirm_pass and len(new_pass) >= 5:
                # Aggiornamento dati locale
                df_dip.loc[df_dip['Nome'] == st.session_state.utente_loggato, 'Password'] = new_pass
                df_dip.loc[df_dip['Nome'] == st.session_state.utente_loggato, 'PrimoAccesso'] = 'FALSE'
                # Scrittura su Google Sheets
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.success("✅ Password aggiornata!")
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo corte (min 5 car).")

else:
    # --- INTERFACCIA UTENTE LOGGATO ---
    st.sidebar.info(f"Utente: {st.session_state.utente_loggato}")
    if st.sidebar.button("Log-out"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Nuova Richiesta", "Gestione Admin"]
    choice = st.sidebar.selectbox("Menu", menu)

    dati_utente = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]

    if choice == "I miei Saldi":
        st.header(f"Saldi di {st.session_state.utente_loggato}")
        st.table(dati_utente[['Ferie', 'ROL']])

    elif choice == "Nuova Richiesta":
        st.header("Invia Richiesta")
        with st.form("req"):
            tipo = st.radio("Tipo", ["Ferie", "ROL", "Permesso"])
            inizio = st.date_input("Inizio")
            fine = st.date_input("Fine")
            submit = st.form_submit_button("Invia")
            if submit:
                # Qui aggiungeremo la logica per salvare la richiesta nel foglio
                st.info("Funzione di salvataggio richiesta in arrivo...")

    elif choice == "Gestione Admin":
        if st.session_state.utente_loggato == "Lorenzo Rossini":
            st.header("Area Admin")
            st.dataframe(df_dip)
            # Qui aggiungeremo il tasto Reset Password per i dipendenti
        else:
            st.error("Accesso negato.")
