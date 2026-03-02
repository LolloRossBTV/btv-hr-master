import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAZIONE PAGINA E STATO ---
st.set_page_config(page_title="Portale BTV", layout="centered")

if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- FUNZIONE EMAIL ---
def send_email(subject, body):
    try:
        creds = st.secrets["emails"]
        msg = MIMEMultipart()
        msg['From'] = creds["sender_email"]
        msg['To'] = creds["receiver_email"]
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(creds["smtp_server"], creds["smtp_port"])
        server.starttls()
        server.login(creds["sender_email"], creds["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"⚠️ Errore Email: Password Google non accettata (Errore 535).")
        return False

# --- CARICAMENTO DATI (Risolve l'errore rosa degli screenshot) ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_dip = df_dip.dropna(subset=['Nome'])
    # Pulizia per evitare l'errore 'Series' object has no attribute 'upper'
    df_dip['Match_Nome'] = df_dip['Nome'].astype(str).str.strip().str.upper()
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip().upper()
except Exception as e:
    st.error(f"❌ Errore Database: {e}")
    st.stop()

# --- LOGICA ACCESSO ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Personale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        u_in = st.text_input("COGNOME NOME").strip().upper()
        p_in = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if u_in in df_dip['Match_Nome'].values:
                idx = df_dip[df_dip['Match_Nome'] == u_in].index[0]
                row = df_dip.iloc[idx]
                pw_db = str(row['Password']).split('.')[0].strip()
                
                if str(p_in).strip() == pw_db:
                    st.session_state.utente_loggato = row['Nome']
                    # Controllo Primo Accesso (1, TRUE, SÌ)
                    if str(row['PrimoAccesso']) in ['1', '1.0', 'TRUE', 'SÌ', 'VERO']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password errata.")
            else:
                st.error("❌ Utente non trovato. Controlla COGNOME NOME.")
    
    else:
        # --- SCHERMATA CAMBIO PASSWORD ---
        st.subheader("🔑 Primo Accesso: Cambio Password")
        st.warning(f"Ciao {st.session_state.utente_loggato}, imposta una password sicura.")
        n_p = st.text_input("Nuova Password", type="password")
        c_p = st.text_input("Conferma Password", type="password")
        if st.button("Salva e Entra"):
            if n_p == c_p and len(n_p) >= 5:
                idx_orig = df_dip[df_dip['Nome'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_orig, 'Password'] = n_p
                df_dip.at[idx_orig, 'PrimoAccesso'] = 'FALSE'
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Match_Nome']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")

else:
    # --- AREA LOGGATA ---
    st.sidebar.success(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        menu.append("Area Admin")
    
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "I miei Saldi":
        st.header("Situazione Personale")
        user_row = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(user_row[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Invia Richiesta":
        st.header("Nuova Richiesta")
        with st.form("invio_form"):
            t = st.selectbox("Tipo", ["Ferie", "ROL", "Permesso"])
            note = st.text_area("Note")
            if st.form_submit_button("Invia"):
                testo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {t}\nNote: {note}"
                if send_email(f"Richiesta {t} - {st.session_state.utente_loggato}", testo):
                    st.success("✅ Email inviata!")
                    st.balloons()

    elif choice == "Area Admin":
        st.header("⚙️ Pannello Amministratore")
        st.dataframe(df_dip.drop(columns=['Match_Nome']))
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("➕ Aggiungi")
            n_new = st.text_input("Nome Cognome").upper()
            c_new = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
            if st.button("Salva Nuovo"):
                new_data = {"Nome": n_new, "Password": "12345", "Contratto": c_new, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_upd = pd.concat([df_dip.drop(columns=['Match_Nome']), pd.DataFrame([new_data])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_upd)
                st.success("Aggiunto!")
                st.rerun()
        
        with col2:
            st.subheader("🗑️ Elimina")
            n_del = st.text_input("Nome da eliminare").upper()
            if st.button("Elimina Definitivamente"):
                df_rem = df_dip[df_dip['Nome'] != n_del].drop(columns=['Match_Nome'])
                conn.update(worksheet="Dipendenti", data=df_rem)
                st.warning("Eliminato.")
                st.rerun()

        st.divider()
        st.subheader("🔐 Reset Password")
        u_res = st.selectbox("Utente", df_dip['Nome'].values)
        if st.button("Reset a 12345"):
            idx_r = df_dip[df_dip['Nome'] == u_res].index[0]
            df_dip.at[idx_r, 'Password'] = '12345'
            df_dip.at[idx_r, 'PrimoAccesso'] = 'TRUE'
            conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Match_Nome']))
            st.success("Reset effettuato.")
