import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE ---
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

# --- 3. FUNZIONE INVIO EMAIL ---
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

# --- 4. CONNESSIONE DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
except Exception as e:
    st.error(f"⚠️ Errore caricamento dati: {e}")
    st.stop()

# --- 5. LOGICA DI ACCESSO (LOGIN MANUALE) ---
if not st.session_state.autenticato:
    st.title("Portale Gestionale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login")
        st.info("Digita COGNOME NOME (es. ROSSINI LORENZO)")
        nome_input = st.text_input("Nome e Cognome")
        pass_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            n_pulito = nome_input.strip().upper()
            if n_pulito in df_dip['Nome'].str.upper().values:
                idx = df_dip[df_dip['Nome'].str.upper() == n_pulito].index[0]
                u_row = df_dip.iloc[idx]
                pass_db = str(u_row['Password']).replace('.0', '').strip()
                p_acc = str(u_row['PrimoAccesso']).strip().upper()
                
                if str(pass_input).strip() == pass_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    if p_acc in ['TRUE', 'SÌ', '1', 'VERO', '1.0']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password errata.")
            else:
                st.error("❌ Utente non trovato.")
    
    else:
        st.subheader("🔒 Cambio Password Obbligatorio")
        n_p = st.text_input("Nuova Password", type="password")
        c_p = st.text_input("Conferma Password", type="password")
        if st.button("Salva e Accedi"):
            if n_p == c_p and len(n_p) >= 5:
                idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato].tolist()[0]
                df_dip.at[idx, 'Password'] = n_p
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()

else:
    # --- 6. INTERFACCIA ---
    st.sidebar.write(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Nuova Richiesta", "Area Admin"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "I miei Saldi":
        st.header("I tuoi Saldi")
        dati_u = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati_u[['Ferie', 'ROL']])

    elif choice == "Nuova Richiesta":
        st.header("Invia Richiesta")
        with st.form("richiesta"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL", "Permesso"])
            note = st.text_area("Note")
            if st.form_submit_button("Invia"):
                if send_email(f"Richiesta {tipo} - {st.session_state.utente_loggato}", note):
                    st.success("Inviata!")
                    st.balloons()

    elif choice == "Area Admin":
        u_log = st.session_state.utente_loggato.upper()
        if "LORENZO" in u_log and "ROSSINI" in u_log:
            st.header("🛠️ Pannello Amministratore")
            st.dataframe(df_dip)
            
            # --- SEZIONE AGGIUNGI RISORSA ---
            st.divider()
            st.subheader("➕ Aggiungi Nuova Risorsa")
            with st.expander("Apri modulo inserimento"):
                nuovo_nome = st.text_input("Cognome e Nome (es. ROSSI MARIO)").upper()
                nuovo_contratto = st.selectbox("Tipo Contratto", ["Guardia", "Fiduciario"])
                if st.button("Salva Nuova Risorsa"):
                    if nuovo_nome and nuovo_nome not in df_dip['Nome'].values:
                        nuova_riga = {
                            "Nome": nuovo_nome,
                            "Password": "12345",
                            "Contratto": nuovo_contratto,
                            "Ferie": 0,
                            "ROL": 0,
                            "PrimoAccesso": "TRUE"
                        }
                        df_dip = pd.concat([df_dip, pd.DataFrame([nuova_riga])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=df_dip)
                        st.success(f"✅ {nuovo_nome} aggiunto con successo!")
                        st.rerun()
                    else:
                        st.error("Nome mancante o già esistente.")

            # --- SEZIONE ELIMINA RISORSA ---
            st.divider()
            st.subheader("🗑️ Elimina Risorsa")
            with st.expander("Apri modulo eliminazione"):
                nome_del = st.text_input("Scrivi NOME COGNOME da eliminare").upper()
                st.warning("Attenzione: l'azione è irreversibile.")
                if st.button("CONFERMA ELIMINAZIONE"):
                    if nome_del in df_dip['Nome'].values:
                        df_dip = df_dip[df_dip['Nome'] != nome_del]
                        conn.update(worksheet="Dipendenti", data=df_dip)
                        st.success(f"🗑️ {nome_del} rimosso dal database.")
                        st.rerun()
                    else:
                        st.error("Nome non trovato.")

            # --- SEZIONE RESET PASSWORD ---
            st.divider()
            st.subheader("🔐 Reset Password")
            nome_res = st.text_input("Scrivi nome per reset a 12345").upper()
            if st.button("Esegui Reset"):
                if nome_res in df_dip['Nome'].values:
                    idx = df_dip[df_dip['Nome'] == nome_res].index[0]
                    df_dip.at[idx, 'Password'] = '12345'
                    df_dip.at[idx, 'PrimoAccesso'] = 'TRUE'
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.success("Reset effettuato!")
        else:
            st.error("Accesso negato.")
