import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="Portale Gestionale BTV", layout="centered")

if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 2. MOTORE EMAIL ---
def send_email(subject, body):
    try:
        creds = st.secrets["emails"]
        msg = MIMEMultipart()
        msg['From'] = creds["sender_email"]
        msg['To'] = creds["receiver_email"]
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(creds["smtp_server"], int(creds["smtp_port"]))
        server.starttls()
        pwd = str(creds["sender_password"]).replace(" ", "").strip()
        server.login(creds["sender_email"], pwd)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Errore Email: {e}")
        return False

# --- 3. CARICAMENTO DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0).dropna(subset=['Nome'])
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.strip()
except Exception as e:
    st.error(f"❌ Errore Database: {e}")
    st.stop()

# --- 4. ACCESSO E SICUREZZA (VERSIONE RESET) ---

# TRAPPOLA DI SICUREZZA: Se l'utente prova ad accedere ai saldi 
# ma ha ancora il flag del cambio obbligatorio, forziamo il logout.
if st.session_state.cambio_obbligatorio and st.session_state.autenticato:
    st.session_state.autenticato = False
    st.rerun()

if not st.session_state.autenticato:
    
    # SEZIONE CAMBIO PASSWORD
    if st.session_state.cambio_obbligatorio:
        st.title("🔑 CAMBIO PASSWORD OBBLIGATORIO")
        st.error(f"Attenzione {st.session_state.utente_loggato}, devi impostare una nuova password.")
        
        # Campi con chiavi nuove per resettare il browser
        n_p_new = st.text_input("Nuova Password", type="password", key="np_final_reset")
        c_p_new = st.text_input("Conferma Password", type="password", key="cp_final_reset")
        
        if st.button("Salva e Attiva Account"):
            if n_p_new == c_p_new and len(n_p_new) >= 5:
                # Aggiornamento Database Google Sheets
                idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx, 'Password'] = n_p_new
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                
                # ORA resettiamo i flag per permettere l'accesso
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("✅ Password aggiornata! Ora verrai reindirizzato.")
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")
        st.stop() # Impedisce di scendere ai saldi

    # SCHERMATA LOGIN
    st.title("🛡️ Accesso BTV")
    u_scelto = st.selectbox("DIPENDENTE", ["--- Seleziona ---"] + sorted(df_dip['Nome_Display'].unique()))
    p_in = st.text_input("PASSWORD ATTUALE", type="password")
    
    if st.button("Accedi"):
        if u_scelto != "--- Seleziona ---":
            idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
            row = df_dip.iloc[idx]
            pw_db = str(row['Password']).split('.')[0].strip()
            
            if str(p_in).strip() == pw_db:
                st.session_state.utente_loggato = str(row['Nome_Display'])
                
                # Verifichiamo il valore nel foglio Google
                stato = str(row['PrimoAccesso']).strip().upper()
                if stato in ['1', '1.0', 'TRUE', 'SÌ', 'VERO']:
                    st.session_state.cambio_obbligatorio = True
                    st.session_state.autenticato = False # Resta fuori dai saldi!
                else:
                    st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password errata")
    st.stop()
# --- 5. AREA PRIVATA ---
else:
    nome_u = str(st.session_state.utente_loggato)
    st.sidebar.success(f"👤 {nome_u}")
    
    menu = ["I miei Saldi", "Invia Richiesta"]
    if "ROSSINI" in nome_u.upper():
        menu.append("Pannello Admin")
    
    scelta = st.sidebar.selectbox("Navigazione", menu)
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    if scelta == "I miei Saldi":
        st.header("Situazione Saldi")
        st.table(df_dip[df_dip['Nome_Display'] == nome_u][['Ferie', 'ROL', 'Contratto']])

    elif scelta == "Invia Richiesta":
        st.header("Nuova Richiesta")
        with st.form("form_richiesta"):
            # MENU PULITO (Senza Malattia e Recupero)
            tipo = st.selectbox("Causale", ["Ferie", "ROL (Permesso Orario)", "Legge 104", "Congedo Parentale"])
            date = st.date_input("Seleziona Date", value=())
            note = st.text_area("Note aggiuntive")
            if st.form_submit_button("Invia ai Responsabili"):
                if len(date) >= 1:
                    testo_d = f"Dal {date[0]} al {date[1]}" if len(date)==2 else f"Giorno {date[0]}"
                    corpo = f"Dipendente: {nome_u}\nTipo: {tipo}\nPeriodo: {testo_d}\nNote: {note}"
                    if send_email(f"RICHIESTA {tipo.upper()} - {nome_u}", corpo):
                        st.success("✅ Inviata correttamente!")
                        st.balloons()
                else:
                    st.error("⚠️ Seleziona le date!")

    elif scelta == "Pannello Admin":
        st.header("⚙️ Amministrazione")
        st.dataframe(df_dip.drop(columns=['Nome_Display']))
