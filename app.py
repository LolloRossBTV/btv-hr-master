import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- INIZIALIZZAZIONE STATO (Risolve AttributeError riga 71) ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

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
            # Individuiamo la riga corretta dell'utente
            utente_row = df_dip.loc[df_dip['Nome'] == nome_utente]
            
            # Pulizia dati (gestione numeri .0 e spazi)
            password_db = str(utente_row.iloc[0]['Password']).replace('.0', '').strip()
            primo_acc = str(utente_row.iloc[0]['PrimoAccesso']).strip().upper()
            
            if str(password_input).strip() == password_db:
                st.session_state.utente_loggato = nome_utente
                # Se è TRUE (o True), obblighiamo al cambio
                if primo_acc in ['TRUE', 'SÌ', '1']:
                    st.session_state.cambio_obbligatorio = True
                    st.rerun()
                else:
                    st.session_state.autenticato = True
                    st.rerun()
            else:
                st.error("❌ Password errata.")
    
    else:
        st.subheader("🔒 Cambio Password Obbligatorio")
        st.info(f"Ciao {st.session_state.utente_loggato}, per sicurezza devi impostare una nuova password.")
        new_pass = st.text_input("Nuova Password", type="password")
        confirm_pass = st.text_input("Conferma Nuova Password", type="password")
        
        if st.button("Salva e Accedi"):
            if new_pass == confirm_pass and len(new_pass) >= 5:
                # Aggiornamento locale e su Google Sheets
                idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato].tolist()[0]
                df_dip.at[idx, 'Password'] = new_pass
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                
                try:
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.success("✅ Password aggiornata con successo!")
                    st.session_state.cambio_obbligatorio = False
                    st.session_state.autenticato = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore nel salvataggio su Google Sheets: {e}")
            else:
                st.error("❌ Le password non coincidono o sono troppo corte (min. 5 caratteri).")

else:
    # --- INTERFACCIA PER UTENTI LOGGATI ---
    st.sidebar.success(f"Connesso: {st.session_state.utente_loggato}")
    if st.sidebar.button("Esci"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Nuova Richiesta", "Area Admin"]
    choice = st.sidebar.selectbox("Cosa vuoi fare?", menu)

    if choice == "I miei Saldi":
        st.header(f"Situazione Ferie/ROL")
        dati_utente = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati_utente[['Ferie', 'ROL']])

    elif choice == "Nuova Richiesta":
        st.header("Compila la richiesta")
        st.write("Funzione in fase di test...")

    elif choice == "Area Admin":
        if st.session_state.utente_loggato == "Lorenzo Rossini":
            st.header("Pannello di Controllo")
            st.dataframe(df_dip)
        else:
            st.error("Spiacente, solo Lorenzo può vedere questa sezione.")
