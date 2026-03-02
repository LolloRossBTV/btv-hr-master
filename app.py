import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. PARAMETRI TECNICI ---
MAT_FERIE_GUARDIA = 1.83
MAT_FERIE_FIDUCIARIO = 1.50
MAT_ROL_FIDUCIARIO = 0.50

# --- 2. STATO SESSIONE ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 3. FUNZIONE EMAIL ---
def send_email(subject, body):
    try:
        # Recupero segreti dai secrets di Streamlit
        SENDER = st.secrets["emails"]["sender_email"]
        PASS = st.secrets["emails"]["sender_password"]
        RECEIVER = st.secrets["emails"]["receiver_email"]
        SMTP_SERVER = st.secrets["emails"]["smtp_server"]
        SMTP_PORT = st.secrets["emails"]["smtp_port"]

        msg = MIMEMultipart()
        msg['From'] = SENDER
        msg['To'] = RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER, PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        # Questo cattura l'errore 535 che vedi nello screenshot
        st.error(f"❌ Errore autenticazione Email: {e}")
        return False

# --- 4. MOTORE MATURAZIONE ---
def calcola_maturazione(df):
    df['Ferie'] = pd.to_numeric(df['Ferie'], errors='coerce').fillna(0)
    df['ROL'] = pd.to_numeric(df['ROL'], errors='coerce').fillna(0)
    for i, r in df.iterrows():
        if r['Contratto'] == "Guardia":
            df.at[i, 'Ferie'] += MAT_FERIE_GUARDIA
        else:
            df.at[i, 'Ferie'] += MAT_FERIE_FIDUCIARIO
            df.at[i, 'ROL'] += MAT_ROL_FIDUCIARIO
    return df

# --- 5. CARICAMENTO DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    
    # Controllo cambio mese
    try:
        conf_df = conn.read(worksheet="Config", ttl=0)
        config = dict(zip(conf_df.key, conf_df.value))
        oggi = datetime.now()
        ultimo = pd.to_datetime(config.get('last_update', '2000-01-01'))
        if oggi.month != ultimo.month or oggi.year != ultimo.year:
            df_dip = calcola_maturazione(df_dip)
            st.info("📅 Nuovo mese: Saldi aggiornati!")
    except:
        pass
except Exception as e:
    st.error(f"Errore DB: {e}")
    st.stop()

# --- 6. INTERFACCIA DI LOGIN ---
if not st.session_state.autenticato:
    st.title("💼 Portale Risorse Umane BTV")
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login Dipendente")
        st.warning("⚠️ Inserire il nome in MAIUSCOLO (es: ROSSINI LORENZO)")
        u_in = st.text_input("Nome e Cognome").strip().upper()
        p_in = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if u_in in df_dip['Nome'].str.upper().values:
                idx = df_dip[df_dip['Nome'].str.upper() == u_in].index[0]
                row = df_dip.iloc[idx]
                if str(p_in) == str(row['Password']).replace('.0', ''):
                    st.session_state.utente_loggato = row['Nome']
                    if str(row['PrimoAccesso']).upper() in ['TRUE', '1', 'SÌ']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else: st.error("Password errata")
            else: st.error("Utente non trovato")
    else:
        st.subheader("🔑 Nuova Password")
        np = st.text_input("Password nuova", type="password")
        if st.button("Salva"):
            idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato][0]
            df_dip.at[idx, 'Password'] = np
            df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
            conn.update(worksheet="Dipendenti", data=df_dip)
            st.session_state.autenticato = True
            st.session_state.cambio_obbligatorio = False
            st.rerun()

else:
    # --- 7. AREA UTENTE ---
    st.sidebar.header(f"Benvenuto {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()
    
    scelta = st.sidebar.radio("Menu", ["Saldi", "Richiesta", "Amministrazione"])

    if scelta == "Saldi":
        st.header("I tuoi contatori")
        st.table(df_dip[df_dip['Nome'] == st.session_state.utente_loggato][['Ferie', 'ROL', 'Contratto']])

    elif scelta == "Richiesta":
        st.header("Invia Ferie/ROL")
        with st.form("f_rich"):
            tipo = st.selectbox("Cosa richiedi?", ["Ferie", "ROL"])
            dal = st.date_input("Inizio")
            al = st.date_input("Fine")
            note = st.text_area("Note")
            if st.form_submit_button("Invia ai Responsabili"):
                testo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {tipo}\nDal: {dal} Al: {al}\nNote: {note}"
                if send_email(f"RICHIESTA PORTALE - {st.session_state.utente_loggato}", testo):
                    st.success("Richiesta inviata via email!")
                    st.balloons()

    elif scelta == "Amministrazione":
        if "LORENZO" in st.session_state.utente_loggato.upper():
            st.header("⚙️ Pannello Admin")
            st.dataframe(df_dip)
            
            # AGGIUNGI
            st.subheader("➕ Nuova Risorsa")
            c1, c2 = st.columns(2)
            n_n = c1.text_input("Cognome Nome nuovo").upper()
            n_c = c2.selectbox("Contratto", ["Guardia", "Fiduciario"], key="new_c")
            if st.button("Aggiungi Dipendente"):
                new_r = {"Nome": n_n, "Password": "12345", "Contratto": n_c, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_dip = pd.concat([df_dip, pd.DataFrame([new_r])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.rerun()

            # ELIMINA
            st.subheader("🗑️ Rimuovi Risorsa")
            n_d = st.text_input("Cognome Nome da eliminare").upper()
            if st.button("ELIMINA ORA"):
                df_dip = df_dip[df_dip['Nome'] != n_d]
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.rerun()

            # RESET
            st.subheader("🔐 Reset Password")
            n_r = st.text_input("Cognome Nome per Reset").upper()
            if st.button("Reset a 12345"):
                df_dip.loc[df_dip['Nome'] == n_r, ['Password', 'PrimoAccesso']] = ['12345', 'TRUE']
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.success("Reset OK")
        else:
            st.error("Accesso negato.")
