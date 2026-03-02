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
        st.error(f"❌ ERRORE AUTENTICAZIONE EMAIL (535): {e}")
        st.warning("⚠️ Nota: Devi usare una 'Password per le app' di Google, non la tua password solita.")
        return False

# --- 4. CARICAMENTO DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    # Pulizia dati per evitare errori di tipo
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip().upper()
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

# --- 5. LOGICA LOGIN ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Personale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login")
        u_input = st.text_input("Inserisci COGNOME NOME").strip().upper()
        p_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if u_input in df_dip['Nome'].str.upper().values:
                idx = df_dip[df_dip['Nome'].str.upper() == u_input].index[0]
                u_row = df_dip.iloc[idx]
                
                # Controllo Password
                pass_db = str(u_row['Password']).replace('.0', '').strip()
                if str(p_input).strip() == pass_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    
                    # CONTROLLO CAMBIO PW (CORRETTO)
                    if u_row['PrimoAccesso'] in ['TRUE', '1', '1.0', 'SÌ', 'VERO']:
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
        st.subheader("🔑 Cambio Password Obbligatorio")
        st.info(f"Ciao {st.session_state.utente_loggato}, devi impostare una password sicura.")
        n_p = st.text_input("Nuova Password", type="password")
        c_p = st.text_input("Conferma Password", type="password")
        
        if st.button("Salva e Accedi"):
            if n_p == c_p and len(n_p) >= 5:
                idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato][0]
                df_dip.at[idx, 'Password'] = n_p
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("Password aggiornata!")
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")

else:
    # --- 6. INTERFACCIA ---
    st.sidebar.success(f"Loggato: {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Richiesta Ferie", "Gestione Admin"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "I miei Saldi":
        st.header("Contatori Personali")
        dati = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Richiesta Ferie":
        st.header("Nuova Richiesta")
        with st.form("form_f"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL"])
            note = st.text_area("Note")
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Dipendente: {st.session_state.utente_loggato}\nTipo: {tipo}\nNote: {note}"
                if send_email(f"RICHIESTA PORTALE - {st.session_state.utente_loggato}", corpo):
                    st.success("Email inviata correttamente!")
                    st.balloons()

    elif choice == "Gestione Admin":
        # CONTROLLO ADMIN UNIVERSALE PER LORENZO
        user_name = st.session_state.utente_loggato.upper()
        if "LORENZO" in user_name and "ROSSINI" in user_name:
            st.header("🛠️ Pannello Amministratore")
            st.dataframe(df_dip)
            
            st.divider()
            st.subheader("➕ Aggiungi / 🗑️ Elimina")
            col_add, col_del = st.columns(2)
            
            with col_add:
                n_new = st.text_input("Nome Nuovo").upper()
                c_new = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
                if st.button("Aggiungi"):
                    new_r = {"Nome": n_new, "Password": "12345", "Contratto": c_new, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                    df_dip = pd.concat([df_dip, pd.DataFrame([new_r])], ignore_index=True)
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.rerun()
            
            with col_del:
                n_del = st.text_input("Nome da eliminare").upper()
                if st.button("Elimina"):
                    df_dip = df_dip[df_dip['Nome'] != n_del]
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.rerun()
            
            st.divider()
            st.subheader("🔐 Reset Password")
            # Menu a tendina per evitare errori di battitura nel reset
            u_reset = st.selectbox("Seleziona dipendente per reset", df_dip['Nome'].values)
            if st.button("Esegui Reset a 12345"):
                df_dip.loc[df_dip['Nome'] == u_reset, ['Password', 'PrimoAccesso']] = ['12345', 'TRUE']
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.success(f"Reset completato per {u_reset}")
        else:
            st.error("⛔ Accesso negato. Solo l'amministratore può accedere a questa sezione.")
