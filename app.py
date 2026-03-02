import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE PARAMETRI MATURAZIONE ---
MAT_FERIE_GUARDIA = 1.83
MAT_FERIE_FIDUCIARIO = 1.50
MAT_ROL_FIDUCIARIO = 0.50

# --- 2. INIZIALIZZAZIONE SESSIONE ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 3. FUNZIONE MOTORE EMAIL ---
def send_email(subject, body):
    try:
        S_EMAIL = st.secrets["emails"]["sender_email"]
        S_PASS = st.secrets["emails"]["sender_password"]
        R_EMAIL = st.secrets["emails"]["receiver_email"]
        
        msg = MIMEMultipart()
        msg['From'] = S_EMAIL
        msg['To'] = R_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(st.secrets["emails"]["smtp_server"], st.secrets["emails"]["smtp_port"])
        server.starttls()
        server.login(S_EMAIL, S_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Errore Email (535): Credenziali non accettate. {e}")
        return False

# --- 4. CARICAMENTO E PULIZIA DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    
    # Risoluzione definitiva errore 'Series' object has no attribute 'upper'
    df_dip['Match_Nome'] = df_dip['Nome'].astype(str).str.strip().str.upper()
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip().upper()
except Exception as e:
    st.error(f"❌ Errore caricamento Database: {e}")
    st.stop()

# --- 5. LOGICA DI ACCESSO E SICUREZZA ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Personale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login Riservato")
        u_in = st.text_input("COGNOME NOME").strip().upper()
        p_in = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if u_in in df_dip['Match_Nome'].values:
                idx = df_dip[df_dip['Match_Nome'] == u_in].index[0]
                u_row = df_dip.iloc[idx]
                
                # Pulizia password da eventuali decimali .0
                pw_db = str(u_row['Password']).split('.')[0].strip()
                
                if str(p_in).strip() == pw_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    
                    # Controllo Cambio Password Obbligatorio
                    if u_row['PrimoAccesso'] in ['1', '1.0', 'TRUE', 'SÌ', 'VERO']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password errata.")
            else:
                st.error("❌ Utente non trovato. Scrivi COGNOME NOME.")
    
    else:
        # --- SCHERMATA CAMBIO PASSWORD ---
        st.subheader("🔑 Primo Accesso: Cambio Password")
        st.warning(f"Ciao {st.session_state.utente_loggato}, devi impostare una password personale.")
        n_p = st.text_input("Nuova Password (min. 5 caratt.)", type="password")
        c_p = st.text_input("Conferma Password", type="password")
        
        if st.button("Salva e Entra"):
            if n_p == c_p and len(n_p) >= 5:
                idx_o = df_dip[df_dip['Nome'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_o, 'Password'] = n_p
                df_dip.at[idx_o, 'PrimoAccesso'] = 'FALSE'
                
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Match_Nome']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")

else:
    # --- 6. INTERFACCIA UTENTE LOGGATO ---
    st.sidebar.success(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        menu.append("Area Admin")
    
    choice = st.sidebar.selectbox("Seleziona", menu)

    if choice == "I miei Saldi":
        st.header("I tuoi Contatori")
        dati = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Invia Richiesta":
        st.header("Nuova Richiesta")
        with st.form("form_rich"):
            t = st.selectbox("Tipo", ["Ferie", "ROL", "Permesso"])
            inizio = st.date_input("Inizio")
            fine = st.date_input("Fine")
            note = st.text_area("Note")
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {t}\nPeriodo: {inizio} - {fine}\nNote: {note}"
                if send_email(f"RICHIESTA PORTALE - {st.session_state.utente_loggato}", corpo):
                    st.success("✅ Email inviata!")
                    st.balloons()

    elif choice == "Area Admin":
        st.header("⚙️ Pannello Amministrazione")
        st.dataframe(df_dip.drop(columns=['Match_Nome']))
        
        # --- AGGIUNGI ---
        st.divider()
        st.subheader("➕ Aggiungi Dipendente")
        with st.expander("Modulo Inserimento"):
            n_new = st.text_input("Cognome Nome").upper()
            c_new = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
            if st.button("Salva Nuovo"):
                new_r = {"Nome": n_new, "Password": "12345", "Contratto": c_new, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_upd = pd.concat([df_dip.drop(columns=['Match_Nome']), pd.DataFrame([new_r])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_upd)
                st.success("✅ Aggiunto!")
                st.rerun()

        # --- ELIMINA ---
        st.divider()
        st.subheader("🗑️ Elimina Dipendente")
        n_del = st.text_input("Nome da eliminare").upper()
        if st.button("Rimuovi Definitivamente"):
            df_rem = df_dip[df_dip['Nome'] != n_del].drop(columns=['Match_Nome'])
            conn.update(worksheet="Dipendenti", data=df_rem)
            st.warning("Eliminato.")
            st.rerun()

        # --- RESET PASSWORD ---
        st.divider()
        st.subheader("🔐 Reset Password")
        u_res = st.selectbox("Seleziona utente", df_dip['Nome'].values)
        if st.button("Esegui Reset a 12345"):
            idx_r = df_dip[df_dip['Nome'] == u_res].index[0]
            df_dip.at[idx_r, 'Password'] = '12345'
            df_dip.at[idx_r, 'PrimoAccesso'] = 'TRUE'
            conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Match_Nome']))
            st.success("✅ Reset completato.")
