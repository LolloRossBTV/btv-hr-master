import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="Portale BTV", layout="centered")

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
    st.error(f"Errore Database: {e}")
    st.stop()

# --- 4. ACCESSO E SICUREZZA ---
if not st.session_state.autenticato:
    if st.session_state.cambio_obbligatorio:
        st.title("🔑 Cambio Password Obbligatorio")
        st.info(f"Utente: {st.session_state.utente_loggato}")
        # Variabili rinominate per evitare NameError
        nuova_pass = st.text_input("Nuova Password", type="password")
        conf_pass = st.text_input("Conferma Password", type="password")
        if st.button("Aggiorna e Accedi"):
            if nuova_pass == conf_pass and len(nuova_pass) >= 5:
                idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx, 'Password'] = nuova_pass
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("Le password non coincidono o sono troppo brevi.")
        st.stop()

    st.title("🛡️ Accesso BTV")
    u_scelto = st.selectbox("DIPENDENTE", ["--- Seleziona ---"] + sorted(df_dip['Nome_Display'].unique()))
    p_in = st.text_input("PASSWORD", type="password")
    if st.button("Entra"):
        if u_scelto != "--- Seleziona ---":
            idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
            row = df_dip.iloc[idx]
            if str(p_in).strip() == str(row['Password']).split('.')[0].strip():
                # Forza stringa per evitare AttributeError
                st.session_state.utente_loggato = str(row['Nome_Display'])
                if str(row['PrimoAccesso']).strip().upper() in ['1', 'TRUE', 'SÌ']:
                    st.session_state.cambio_obbligatorio = True
                else:
                    st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("Password errata")
    st.stop()

# --- 5. AREA PRIVATA ---
else:
    nome_corrente = str(st.session_state.utente_loggato)
    st.sidebar.success(f"👤 {nome_corrente}")
    
    opzioni = ["I miei Saldi", "Invia Richiesta"]
    if "ROSSINI" in nome_corrente.upper():
        opzioni.append("Pannello Admin")
    
    scelta = st.sidebar.selectbox("Menu", opzioni)
    if st.sidebar.button("Esci"):
        st.session_state.autenticato = False
        st.rerun()

    if scelta == "I miei Saldi":
        st.header("I tuoi contatori")
        st.table(df_dip[df_dip['Nome_Display'] == nome_corrente][['Ferie', 'ROL', 'Contratto']])

    elif scelta == "Invia Richiesta":
        st.header("Modulo Richiesta")
        with st.form("invio_form"):
            # Menu pulito come da richiesta
            tipo = st.selectbox("Causale", ["Ferie", "ROL (Permesso Orario)", "Legge 104", "Congedo Parentale"])
            date = st.date_input("Periodo", value=())
            note = st.text_area("Note")
            if st.form_submit_button("Invia"):
                if len(date) >= 1:
                    testo_date = f"Dal {date[0]} al {date[1]}" if len(date)==2 else f"Giorno {date[0]}"
                    msg = f"Dipendente: {nome_corrente}\nTipo: {tipo}\nPeriodo: {testo_date}\nNote: {note}"
                    if send_email(f"RICHIESTA {tipo.upper()} - {nome_corrente}", msg):
                        st.success("Inviata!")
                        st.balloons()
                else:
                    st.error("Scegli le date!")

    elif scelta == "Pannello Admin":
        st.header("Gestione Personale")
        st.dataframe(df_dip.drop(columns=['Nome_Display']))
