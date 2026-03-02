import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE STATO ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None

# --- 2. FUNZIONE EMAIL (Gestione robusta errore 535) ---
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
        st.error(f"❌ ERRORE EMAIL: Le credenziali Google nei Secrets non sono corrette (Errore 535).")
        return False

# --- 3. CARICAMENTO DATI (Correzione Errore 'Series') ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    # Creiamo una colonna di confronto sicura per evitare crash 'upper'
    df_dip['Match'] = df_dip['Nome'].astype(str).str.upper().str.strip()
except Exception as e:
    st.error(f"❌ Errore critico database: {e}")
    st.stop()

# --- 4. INTERFACCIA DI LOGIN ---
if not st.session_state.autenticato:
    st.title("🛡️ Accesso Portale BTV")
    u_in = st.text_input("Inserisci COGNOME NOME").strip().upper()
    p_in = st.text_input("Password", type="password")
    
    if st.button("Accedi"):
        if u_in in df_dip['Match'].values:
            idx = df_dip[df_dip['Match'] == u_in].index[0]
            row = df_dip.iloc[idx]
            # Pulizia password (toglie eventuali .0 finali)
            pw_db = str(row['Password']).split('.')[0].strip()
            
            if str(p_in).strip() == pw_db:
                st.session_state.utente_loggato = row['Nome']
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password errata.")
        else:
            st.error("❌ Utente non trovato. Controlla lo spelling nel foglio Google.")

else:
    # --- 5. AREA UTENTE LOGGATO ---
    st.sidebar.success(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Richiesta Ferie/ROL"]
    # Aggiungi Area Admin solo per Lorenzo
    if "LORENZO" in st.session_state.utente_loggato.upper():
        menu.append("Area Admin")
    
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "I miei Saldi":
        st.header("Situazione Contatori")
        user_data = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(user_data[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Richiesta Ferie/ROL":
        st.header("Invia Richiesta")
        with st.form("form_invio"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL"])
            note = st.text_area("Note")
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Dipendente: {st.session_state.utente_loggato}\nTipo: {tipo}\nNote: {note}"
                if send_email(f"RICHIESTA DA PORTALE - {st.session_state.utente_loggato}", corpo):
                    st.success("✅ Email inviata con successo!")
                    st.balloons()

    elif choice == "Area Admin":
        st.header("⚙️ Gestione Database")
        st.dataframe(df_dip.drop(columns=['Match']))
