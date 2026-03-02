import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. STATO SESSIONE ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 2. FUNZIONE EMAIL ---
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
        st.error(f"❌ Errore Email (535): Password rifiutata. {e}")
        return False

# --- 3. CARICAMENTO DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    # Pulizia nomi per evitare crash 'Series'
    df_dip['Match_Nome'] = df_dip['Nome'].astype(str).str.strip().str.upper()
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip().upper()
except Exception as e:
    st.error(f"❌ Errore Database: {e}")
    st.stop()

# --- 4. LOGICA LOGIN ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Gestionale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login")
        nome_in = st.text_input("COGNOME NOME").strip().upper()
        pass_in = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if nome_in in df_dip['Match_Nome'].values:
                idx = df_dip[df_dip['Match_Nome'] == nome_in].index[0]
                u_row = df_dip.iloc[idx]
                pw_db = str(u_row['Password']).split('.')[0].strip()
                
                if str(pass_in).strip() == pw_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    # Controllo cambio password obbligatorio (colonna PrimoAccesso = 1 o TRUE)
                    if str(u_row['PrimoAccesso']) in ['1', '1.0', 'TRUE', 'SÌ']:
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
        # --- SCHERMATA CAMBIO PASSWORD ---
        st.subheader("🔑 Cambio Password Obbligatorio")
        st.info(f"Ciao {st.session_state.utente_loggato}, imposta una nuova password.")
        new_p = st.text_input("Nuova Password", type="password")
        conf_p = st.text_input("Conferma Password", type="password")
        if st.button("Salva e Accedi"):
            if new_p == conf_p and len(new_p) >= 5:
                idx_orig = df_dip[df_dip['Nome'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_orig, 'Password'] = new_p
                df_dip.at[idx_orig, 'PrimoAccesso'] = 'FALSE'
                df_save = df_dip.drop(columns=['Match_Nome'])
                conn.update(worksheet="Dipendenti", data=df_save)
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password non valide.")

else:
    # --- 5. INTERFACCIA PRINCIPALE ---
    st.sidebar.success(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    # Logica Menu Admin
    menu = ["I miei Saldi", "Richiesta Ferie/ROL"]
    u_log = st.session_state.utente_loggato.upper()
    if "ROSSINI" in u_log and "LORENZO" in u_log:
        menu.append("Area Admin")
    
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "I miei Saldi":
        st.header("Situazione Attuale")
        dati = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Richiesta Ferie/ROL":
        st.header("Nuova Richiesta")
        with st.form("form_invio"):
            t = st.selectbox("Tipo", ["Ferie", "ROL"])
            note = st.text_area("Note")
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {t}\nNote: {note}"
                if send_email(f"RICHIESTA - {st.session_state.utente_loggato}", corpo):
                    st.success("✅ Email inviata!")
                    st.balloons()

    elif choice == "Area Admin":
        st.header("⚙️ Strumenti Amministratore")
        st.dataframe(df_dip.drop(columns=['Match_Nome']))
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("➕ Aggiungi Dipendente")
            n_new = st.text_input("Nome e Cognome").upper()
            c_new = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
            if st.button("Aggiungi"):
                new_r = {"Nome": n_new, "Password": "12345", "Contratto": c_new, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_upd = pd.concat([df_dip.drop(columns=['Match_Nome']), pd.DataFrame([new_r])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_upd)
                st.success("Aggiunto!")
                st.rerun()

        with col2:
            st.subheader("🗑️ Elimina Dipendente")
            n_del = st.text_input("Nome da eliminare").upper()
            if st.button("Elimina"):
                df_rem = df_dip[df_dip['Nome'] != n_del].drop(columns=['Match_Nome'])
                conn.update(worksheet="Dipendenti", data=df_rem)
                st.warning("Eliminato.")
                st.rerun()

        st.divider()
        st.subheader("🔐 Reset Password")
        u_res = st.selectbox("Seleziona dipendente", df_dip['Nome'].values)
        if st.button("Reset a 12345"):
            idx_r = df_dip[df_dip['Nome'] == u_res].index[0]
            df_dip.at[idx_r, 'Password'] = '12345'
            df_dip.at[idx_r, 'PrimoAccesso'] = 'TRUE'
            conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Match_Nome']))
            st.success("Reset OK")
