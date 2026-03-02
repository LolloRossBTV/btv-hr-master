import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- STATO SESSIONE ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None

# --- FUNZIONE EMAIL (Gestione errore 535) ---
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
        # Questo cattura l'errore 535 che vedi negli screenshot
        st.error(f"❌ Errore Invio: {e}") 
        return False

# --- CARICAMENTO DATI (Senza errore 'Series') ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Dipendenti", ttl=0)
    # Trasformiamo la colonna in stringhe pulite PRIMA di confrontarle
    df['Nome_Clean'] = df['Nome'].astype(str).str.upper().str.strip()
except Exception as e:
    st.error(f"❌ Errore caricamento database: {e}")
    st.stop()

# --- INTERFACCIA ---
if not st.session_state.autenticato:
    st.title("🛡️ Accesso BTV")
    u_in = st.text_input("Cognome Nome").strip().upper()
    p_in = st.text_input("Password", type="password")
    
    if st.button("Accedi"):
        if u_in in df['Nome_Clean'].values:
            idx = df[df['Nome_Clean'] == u_in].index[0]
            # Pulizia password da eventuali .0 di Excel
            pw_db = str(df.iloc[idx]['Password']).split('.')[0].strip()
            
            if str(p_in).strip() == pw_corretta:
                st.session_state.utente_loggato = df.iloc[idx]['Nome']
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password errata")
        else:
            st.error("❌ Utente non trovato")
else:
    st.sidebar.write(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()
    
    # Visualizzazione Saldi
    st.header("I tuoi Saldi")
    mie_ferie = df[df['Nome'] == st.session_state.utente_loggato]
    st.table(mie_ferie[['Ferie', 'ROL', 'Contratto']])
    
    # Invio Richiesta
    st.divider()
    with st.form("richiesta"):
        tipo = st.selectbox("Cosa richiedi?", ["Ferie", "ROL"])
        note = st.text_area("Note")
        if st.form_submit_button("Invia ai Responsabili"):
            testo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {tipo}\nNote: {note}"
            if send_email(f"Richiesta {tipo} - {st.session_state.utente_loggato}", testo):
                st.success("✅ Richiesta inviata!")
                st.balloons()
