import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAZIONE ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False

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
        # Gestisce l'errore che vedi negli screen 5f3dbc, 5ed480, 5ed0a5, 5ecc43
        st.error(f"❌ Errore 535: Password Google non accettata. Verifica i Secrets.")
        return False

# --- CARICAMENTO DATI (Correzione Errore 'Series') ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Dipendenti", ttl=0)
    # Risolve l'errore 'Series' object has no attribute 'upper'
    df['Nome_Match'] = df['Nome'].astype(str).str.upper().str.strip()
except Exception as e:
    st.error(f"❌ Errore Database: {e}")
    st.stop()

# --- INTERFACCIA LOGIN ---
if not st.session_state.autenticato:
    st.title("🛡️ Accesso BTV")
    # Istruzione chiara per Lorenzo
    st.info("💡 Scrivi il nome ESATTAMENTE come nel foglio (es: ROSSINI LORENZO)")
    u_in = st.text_input("Cognome Nome").strip().upper()
    p_in = st.text_input("Password", type="password")
    
    if st.button("Accedi"):
        if u_in in df['Nome_Match'].values:
            idx = df[df['Nome_Match'] == u_in].index[0]
            # Gestione password numeriche
            pw_db = str(df.iloc[idx]['Password']).split('.')[0].strip()
            
            if str(p_in).strip() == pw_db:
                st.session_state.utente_loggato = df.iloc[idx]['Nome']
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password errata")
        else:
            # Errore che vedi in image_f9755f
            st.error(f"❌ Utente '{u_in}' non trovato nel database.")
else:
    st.sidebar.write(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()
    
    st.header("Situazione Personale")
    st.table(df[df['Nome'] == st.session_state.utente_loggato][['Ferie', 'ROL', 'Contratto']])
    
    # Form per invio email
    with st.form("invio"):
        t = st.selectbox("Tipo", ["Ferie", "ROL"])
        note = st.text_area("Note")
        if st.form_submit_button("Invia"):
            testo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {t}\nNote: {note}"
            if send_email(f"Richiesta {t} - {st.session_state.utente_loggato}", testo):
                st.success("✅ Inviata!")
                st.balloons()
