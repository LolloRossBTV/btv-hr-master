import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="Portale Gestionale BTV", layout="centered")

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
    st.error(f"❌ Errore Database: {e}")
    st.stop()

# --- 4. ACCESSO E SICUREZZA ---
if not st.session_state.autenticato:
    if st.session_state.cambio_obbligatorio:
        st.title("🔑 Cambio Password Obbligatorio")
        st.warning(f"Profilo: {st.session_state.utente_loggato}")
        
        n_p = st.text_input("Nuova Password (min. 5 car.)", type="password", key="np_new")
        c_p = st.text_input("Conferma Password", type="password", key="cp_new")
        
        if st.button("Salva e Accedi"):
            if n_p == c_p and len(n_p) >= 5:
                idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx, 'Password'] = n_p
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE' # Scrive FALSE per i prossimi accessi
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password non valide.")
        st.stop()

    st.title("🛡️ Accesso BTV")
    u_scelto = st.selectbox("DIPENDENTE", ["--- Seleziona ---"] + sorted(df_dip['Nome_Display'].unique()))
    p_in = st.text_input("PASSWORD", type="password")
    
    if st.button("Entra"):
        if u_scelto != "--- Seleziona ---":
            idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
            row = df_dip.iloc[idx]
            pw_db = str(row['Password']).split('.')[0].strip()
            
            if str(p_in).strip() == pw_db:
                st.session_state.utente_loggato = str(row['Nome_Display'])
                
                # CORREZIONE: Legge 1, 1.0 o TRUE come primo accesso
                valore_primo = str(row['PrimoAccesso']).strip().upper()
                if valore_primo in ['1', '1.0', 'TRUE', 'SÌ']:
                    st.session_state.cambio_obbligatorio = True
                else:
                    st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password errata")
    st.stop()
# --- 5. AREA PRIVATA ---
else:
    nome_u = str(st.session_state.utente_loggato)
    st.sidebar.success(f"👤 {nome_u}")
    
    menu = ["I miei Saldi", "Invia Richiesta"]
    if "ROSSINI" in nome_u.upper():
        menu.append("Pannello Admin")
    
    scelta = st.sidebar.selectbox("Navigazione", menu)
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    if scelta == "I miei Saldi":
        st.header("Situazione Saldi")
        st.table(df_dip[df_dip['Nome_Display'] == nome_u][['Ferie', 'ROL', 'Contratto']])

    elif scelta == "Invia Richiesta":
        st.header("Nuova Richiesta")
        with st.form("form_richiesta"):
            # MENU PULITO (Senza Malattia e Recupero)
            tipo = st.selectbox("Causale", ["Ferie", "ROL (Permesso Orario)", "Legge 104", "Congedo Parentale"])
            date = st.date_input("Seleziona Date", value=())
            note = st.text_area("Note aggiuntive")
            if st.form_submit_button("Invia ai Responsabili"):
                if len(date) >= 1:
                    testo_d = f"Dal {date[0]} al {date[1]}" if len(date)==2 else f"Giorno {date[0]}"
                    corpo = f"Dipendente: {nome_u}\nTipo: {tipo}\nPeriodo: {testo_d}\nNote: {note}"
                    if send_email(f"RICHIESTA {tipo.upper()} - {nome_u}", corpo):
                        st.success("✅ Inviata correttamente!")
                        st.balloons()
                else:
                    st.error("⚠️ Seleziona le date!")

    elif scelta == "Pannello Admin":
        # CANCELLA QUELLO CHE C'È QUI E INCOLLA:
        st.header("⚙️ Gestione Personale e Database")
        
        # 1. Visualizzazione Tabella Completa
        st.subheader("Anagrafica Dipendenti")
        st.dataframe(df_dip.drop(columns=['Nome_Display']), use_container_width=True)
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 2. Reset Utente (Password e Primo Accesso)
            st.subheader("🔄 Reset Utente")
            u_reset = st.selectbox("Seleziona Dipendente da resettare", sorted(df_dip['Nome_Display'].unique()))
            if st.button("Forza Cambio Password"):
                idx = df_dip[df_dip['Nome_Display'] == u_reset].index[0]
                df_dip.at[idx, 'Password'] = "12345"
                df_dip.at[idx, 'PrimoAccesso'] = "1"
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.success(f"✅ {u_reset} resettato! Password provvisoria: 12345")
                st.rerun()

        with col2:
            # 3. Eliminazione Dipendente
            st.subheader("🗑️ Elimina Risorsa")
            u_del = st.selectbox("Seleziona chi rimuovere", ["---"] + sorted(df_dip['Nome_Display'].unique()))
            if st.button("Elimina Definitivamente", type="primary"):
                if u_del != "---":
                    df_final = df_dip[df_dip['Nome_Display'] != u_del].drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_final)
                    st.warning(f"Utente {u_del} rimosso.")
                    st.rerun()

        st.divider()
        
        # 4. Aggiunta Nuovo Dipendente
        st.subheader("➕ Aggiungi Nuova Risorsa")
        with st.form("nuovo_utente"):
            n_nome = st.text_input("Nome e Cognome (es: BIANCHI MARIO)").upper()
            n_contratto = st.selectbox("Contratto", ["Fiduciario", "Armato", "Amministrativo"])
            n_ferie = st.number_input("Ferie Iniziali", value=0)
            n_rol = st.number_input("ROL Iniziali", value=0)
            
            if st.form_submit_button("Salva nel Database"):
                if n_nome:
                    nuovo_rigo = {
                        "Nome": n_nome,
                        "Password": "12345",
                        "Ferie": n_ferie,
                        "ROL": n_rol,
                        "Contratto": n_contratto,
                        "PrimoAccesso": "1"
                    }
                    df_nuovo = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo_rigo])], ignore_index=True)
                    conn.update(worksheet="Dipendenti", data=df_nuovo)
                    st.success(f"✅ {n_nome} aggiunto con password 12345")
                    st.rerun()
