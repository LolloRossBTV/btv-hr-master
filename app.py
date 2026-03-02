import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE PARAMETRI ---
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

# --- 3. FUNZIONE MOTORE EMAIL ---
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
        st.error(f"❌ Errore Email (Credenziali 535): {e}")
        return False

# --- 4. CARICAMENTO E PULIZIA DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    # Colonna di servizio per il match senza errori 'Series' object
    df_dip['Nome_Match'] = df_dip['Nome'].astype(str).str.strip().str.upper()
    
    # Pulizia PrimoAccesso
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip().upper()
except Exception as e:
    st.error(f"❌ Errore Database: {e}")
    st.stop()

# --- 5. LOGICA ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Personale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login Riservato")
        nome_in = st.text_input("Inserisci COGNOME NOME").strip().upper()
        pass_in = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if nome_in in df_dip['Nome_Match'].values:
                idx = df_dip[df_dip['Nome_Match'] == nome_in].index[0]
                u_row = df_dip.iloc[idx]
                
                # Gestione password
                pw_db = str(u_row['Password']).split('.')[0].strip()
                
                if str(pass_in).strip() == pw_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    
                    # CONTROLLO FORZATO CAMBIO PASSWORD
                    if u_row['PrimoAccesso'] in ['1', '1.0', 'TRUE', 'VERO', 'SÌ']:
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
        st.subheader("🔑 Primo Accesso: Cambio Password")
        st.warning(f"Ciao {st.session_state.utente_loggato}, imposta una nuova password obbligatoria.")
        new_p = st.text_input("Nuova Password", type="password")
        conf_p = st.text_input("Conferma Password", type="password")
        
        if st.button("Salva Password e Entra"):
            if new_p == conf_p and len(new_p) >= 5:
                idx_orig = df_dip[df_dip['Nome'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_orig, 'Password'] = new_p
                df_dip.at[idx_orig, 'PrimoAccesso'] = 'FALSE'
                
                df_save = df_dip.drop(columns=['Nome_Match'])
                conn.update(worksheet="Dipendenti", data=df_save)
                
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("✅ Password aggiornata!")
                st.rerun()
            else:
                st.error("❌ Errore: le password non coincidono o sono troppo brevi.")

else:
    # --- 6. INTERFACCIA PRINCIPALE ---
    st.sidebar.success(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Esci (Logout)"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Invia Richiesta", "Gestione Admin"]
    choice = st.sidebar.selectbox("Naviga nel menu", menu)

    if choice == "I miei Saldi":
        st.header("Situazione Personale")
        dati = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Invia Richiesta":
        st.header("Nuova Richiesta Ferie/ROL")
        with st.form("form_rich"):
            tipo = st.selectbox("Cosa richiedi?", ["Ferie", "ROL", "Permesso"])
            inizio = st.date_input("Dal")
            fine = st.date_input("Al")
            note = st.text_area("Note aggiuntive")
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {tipo}\nPeriodo: {inizio} - {fine}\nNote: {note}"
                if send_email(f"RICHIESTA PORTALE - {st.session_state.utente_loggato}", corpo):
                    st.success("✅ Richiesta inviata via email!")
                    st.balloons()

    elif choice == "Gestione Admin":
        # Controllo Accesso Lorenzo
        u_log = st.session_state.utente_loggato.upper()
        if "LORENZO" in u_log and "ROSSINI" in u_log:
            st.header("⚙️ Area Amministrazione")
            st.dataframe(df_dip.drop(columns=['Nome_Match']))
            
            # --- AGGIUNGI ---
            st.divider()
            st.subheader("➕ Aggiungi Dipendente")
            with st.expander("Apri Form Inserimento"):
                n_new = st.text_input("Nome e Cognome nuovo").upper()
                c_new = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
                if st.button("Salva Nuovo Dipendente"):
                    if n_new:
                        new_r = {"Nome": n_new, "Password": "12345", "Contratto": c_new, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                        df_upd = pd.concat([df_dip.drop(columns=['Nome_Match']), pd.DataFrame([new_r])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=df_upd)
                        st.success(f"✅ {n_new} aggiunto!")
                        st.rerun()

            # --- ELIMINA ---
            st.divider()
            st.subheader("🗑️ Elimina Dipendente")
            with st.expander("Apri Form Rimozione"):
                n_del = st.text_input("Scrivi nome esatto da eliminare").upper()
                if st.button("CONFERMA ELIMINAZIONE"):
                    if n_del in df_dip['Nome'].values:
                        df_rem = df_dip[df_dip['Nome'] != n_del].drop(columns=['Nome_Match'])
                        conn.update(worksheet="Dipendenti", data=df_rem)
                        st.warning(f"🗑️ {n_del} eliminato.")
                        st.rerun()

            # --- RESET ---
            st.divider()
            st.subheader("🔐 Reset Password")
            u_res = st.selectbox("Seleziona per reset a 12345", df_dip['Nome'].values)
            if st.button("Esegui Reset"):
                idx_r = df_dip[df_dip['Nome'] == u_res].index[0]
                df_dip.at[idx_r, 'Password'] = '12345'
                df_dip.at[idx_r, 'PrimoAccesso'] = 'TRUE'
                df_save = df_dip.drop(columns=['Nome_Match'])
                conn.update(worksheet="Dipendenti", data=df_save)
                st.success(f"✅ Password di {u_res} resettata!")
        else:
            st.error("⛔ Accesso negato all'area Admin.")
