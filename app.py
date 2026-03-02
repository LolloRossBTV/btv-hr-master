import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE E PARAMETRI ---
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
        # Questo cattura l'errore 535 BadCredentials degli screenshot
        st.error(f"❌ Errore autenticazione Email: {e}")
        st.info("💡 Suggerimento: Verifica di aver usato una 'Password per le App' di Google, non la tua password normale.")
        return False

# --- 4. CARICAMENTO DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
except Exception as e:
    st.error(f"❌ Errore critico database: {e}")
    st.stop()

# --- 5. SCHERMATA DI LOGIN (MANUALE) ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Personale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Accesso Utente")
        st.info("Scrivi il tuo nome come nel foglio (es: ROSSINI LORENZO)")
        u_input = st.text_input("Nome e Cognome").strip().upper()
        p_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            # Cerchiamo l'utente ignorando maiuscole/minuscole
            if u_input in df_dip['Nome'].str.upper().values:
                idx = df_dip[df_dip['Nome'].str.upper() == u_input].index[0]
                u_row = df_dip.iloc[idx]
                
                # Pulizia password da eventuali .0 di Excel
                pass_db = str(u_row['Password']).replace('.0', '').strip()
                
                if str(p_input).strip() == pass_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    # Controllo primo accesso
                    is_primo = str(u_row['PrimoAccesso']).upper() in ['TRUE', '1', 'SÌ', 'VERO']
                    
                    if is_primo:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password non corretta.")
            else:
                st.error("❌ Utente non trovato. Controlla lo spelling.")
    
    else:
        st.subheader("🔑 Imposta Nuova Password")
        st.warning("Devi cambiare la password predefinita per continuare.")
        nuova_p = st.text_input("Nuova Password", type="password")
        conf_p = st.text_input("Conferma Password", type="password")
        
        if st.button("Salva e Accedi"):
            if nuova_p == conf_p and len(nuova_p) >= 5:
                # Aggiornamento su foglio
                idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato][0]
                df_dip.at[idx, 'Password'] = nuova_p
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                conn.update(worksheet="Dipendenti", data=df_dip)
                
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")

else:
    # --- 6. INTERFACCIA PRINCIPALE ---
    st.sidebar.success(f"👤 Utente: {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Invia Richiesta", "Gestione Admin"]
    choice = st.sidebar.selectbox("Cosa vuoi fare?", menu)

    if choice == "I miei Saldi":
        st.header(f"Saldi di {st.session_state.utente_loggato}")
        dati_u = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati_u[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Invia Richiesta":
        st.header("Compila Richiesta")
        with st.form("richiesta_form"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL", "Permesso"])
            dal = st.date_input("Inizio")
            al = st.date_input("Fine")
            note = st.text_area("Note aggiuntive")
            
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {tipo}\nDal: {dal} Al: {al}\nNote: {note}"
                if send_email(f"RICHIESTA {tipo.upper()} - {st.session_state.utente_loggato}", corpo):
                    st.success("✅ Richiesta inviata via email!")
                    st.balloons()
                else:
                    st.error("❌ Impossibile inviare l'email.")

    elif choice == "Gestione Admin":
        # CONTROLLO PERMESSI ADMIN MIGLIORATO
        nome_clean = st.session_state.utente_loggato.upper()
        if "LORENZO" in nome_clean and "ROSSINI" in nome_clean:
            st.header("⚙️ Pannello di Controllo Admin")
            st.subheader("Riepilogo Dipendenti")
            st.dataframe(df_dip)
            
            # --- AGGIUNGI RISORSA ---
            st.divider()
            st.subheader("➕ Aggiungi Dipendente")
            with st.expander("Apri modulo"):
                new_n = st.text_input("Cognome Nome").upper()
                new_c = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
                if st.button("Salva Nuovo"):
                    if new_n:
                        new_r = {"Nome": new_n, "Password": "12345", "Contratto": new_c, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                        df_dip = pd.concat([df_dip, pd.DataFrame([new_r])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=df_dip)
                        st.success(f"Aggiunto {new_n}")
                        st.rerun()

            # --- ELIMINA RISORSA ---
            st.divider()
            st.subheader("🗑️ Elimina Dipendente")
            with st.expander("Apri modulo rimozione"):
                n_del = st.text_input("Scrivi nome da eliminare").upper()
                if st.button("ELIMINA DEFINITIVAMENTE"):
                    if n_del in df_dip['Nome'].values:
                        df_dip = df_dip[df_dip['Nome'] != n_del]
                        conn.update(worksheet="Dipendenti", data=df_dip)
                        st.warning(f"Rimosso {n_del}")
                        st.rerun()

            # --- RESET PASSWORD ---
            st.divider()
            st.subheader("🔐 Reset Password")
            n_res = st.text_input("Nome per reset a 12345").upper()
            if st.button("Esegui Reset"):
                if n_res in df_dip['Nome'].values:
                    df_dip.loc[df_dip['Nome'] == n_res, ['Password', 'PrimoAccesso']] = ['12345', 'TRUE']
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.success(f"Password di {n_res} resettata.")
        else:
            st.error("⛔ Accesso negato. Solo l'amministratore (L. Rossini) può accedere.")
