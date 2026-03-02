import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Portale BTV", layout="centered")

if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- MOTORE EMAIL ---
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
    except Exception:
        st.error("❌ Errore Email: Controlla la 'Password per le app' nei Secrets.")
        return False

# --- CARICAMENTO DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0).dropna(subset=['Nome'])
    # Pulizia nomi per il menu e per il confronto
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.strip()
except Exception as e:
    st.error(f"❌ Errore Database: {e}")
    st.stop()

# --- LOGICA ACCESSO ---
if not st.session_state.autenticato:
    st.title("🛡️ Accesso Portale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Seleziona il tuo nome e inserisci la password")
        
        # MENU A TENDINA: Niente più errori di battitura o maiuscole
        lista_nomi = sorted(df_dip['Nome_Display'].unique())
        u_scelto = st.selectbox("CHI SEI?", ["Seleziona il tuo nome..."] + lista_nomi)
        p_in = st.text_input("PASSWORD", type="password")
        
        if st.button("Accedi"):
            if u_scelto != "Seleziona il tuo nome...":
                idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
                row = df_dip.iloc[idx]
                
                # Pulizia password da Excel (.0)
                pw_db = str(row['Password']).split('.')[0].strip()
                
                if str(p_in).strip() == pw_db:
                    st.session_state.utente_loggato = row['Nome_Display']
                    
                    # Controllo Primo Accesso
                    p_acc = str(row['PrimoAccesso']).strip().upper()
                    if p_acc in ['1', '1.0', 'TRUE', 'SÌ', 'VERO']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password errata.")
            else:
                st.warning("⚠️ Seleziona prima il tuo nome dal menu.")
    
    else:
        # --- SCHERMATA CAMBIO PASSWORD ---
        st.subheader("🔑 Primo Accesso: Cambio Password")
        st.info(f"Ciao {st.session_state.utente_loggato}, imposta una nuova password.")
        n_p = st.text_input("Nuova Password", type="password")
        c_p = st.text_input("Conferma Password", type="password")
        
        if st.button("Salva e Accedi"):
            if n_p == c_p and len(n_p) >= 5:
                idx_o = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_o, 'Password'] = n_p
                df_dip.at[idx_o, 'PrimoAccesso'] = 'FALSE'
                
                # Update su Google Sheets
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password non valide (minimo 5 caratteri).")

else:
    # --- INTERFACCIA UTENTE ---
    st.sidebar.success(f"👤 {st.session_state.utente_loggato}")
    
    menu = ["I miei Saldi", "Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        menu.append("Pannello Admin")
    
    choice = st.sidebar.selectbox("Menu", menu)
    
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    if choice == "I miei Saldi":
        st.header("Situazione Ferie / ROL")
        user_row = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato]
        st.table(user_row[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Invia Richiesta":
        st.header("Nuova Richiesta")
        with st.form("invio_richiesta"):
            t = st.selectbox("Tipo", ["Ferie", "ROL", "Permesso"])
            note = st.text_area("Note (date e orari)")
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {t}\nNote: {note}"
                if send_email(f"RICHIESTA {t} - {st.session_state.utente_loggato}", corpo):
                    st.success("✅ Email inviata con successo!")
                    st.balloons()

    elif choice == "Pannello Admin":
        st.header("⚙️ Admin")
        st.dataframe(df_dip.drop(columns=['Nome_Display']))
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("➕ Aggiungi")
            n_new = st.text_input("Nuovo Nome e Cognome").strip()
            if st.button("Aggiungi Dipendente"):
                new = {"Nome": n_new, "Password": "12345", "Contratto": "Fiduciario", "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_upd = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([new])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_upd)
                st.rerun()
        with col2:
            st.subheader("🗑️ Elimina")
            n_del = st.selectbox("Seleziona chi eliminare", lista_nomi)
            if st.button("Rimuovi"):
                df_rem = df_dip[df_dip['Nome_Display'] != n_del].drop(columns=['Nome_Display'])
                conn.update(worksheet="Dipendenti", data=df_rem)
                st.rerun()
