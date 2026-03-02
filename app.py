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

# --- 2. INIZIALIZZAZIONE STATO DELL'APP ---
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
        st.error(f"⚠️ Errore critico invio email: {e}")
        return False

# --- 4. FUNZIONE MATURAZIONE SALDI ---
def applica_maturazione(df):
    df['Ferie'] = pd.to_numeric(df['Ferie'], errors='coerce').fillna(0)
    df['ROL'] = pd.to_numeric(df['ROL'], errors='coerce').fillna(0)
    for idx, row in df.iterrows():
        if row['Contratto'] == "Guardia":
            df.at[idx, 'Ferie'] += MAT_FERIE_GUARDIA
        else:
            df.at[idx, 'Ferie'] += MAT_FERIE_FIDUCIARIO
            df.at[idx, 'ROL'] += MAT_ROL_FIDUCIARIO
    return df

# --- 5. CONNESSIONE E CONTROLLO MENSILE ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    
    # Controllo se è necessario aggiornare i saldi (cambio mese)
    try:
        config_df = conn.read(worksheet="Config", ttl=0)
        config = dict(zip(config_df.key, config_df.value))
        oggi = datetime.now()
        ultimo_agg = pd.to_datetime(config.get('last_update', '2000-01-01'))
        
        if oggi.month != ultimo_agg.month or oggi.year != ultimo_agg.year:
            df_dip = applica_maturazione(df_dip)
            st.info("🔄 Cambio mese rilevato: Saldi aggiornati automaticamente.")
            # Nota: qui servirebbe la scrittura sulla tabella Config per salvare la data
    except:
        pass # Ignora se mancano tabelle di config secondarie
except Exception as e:
    st.error(f"❌ Errore connessione Database: {e}")
    st.stop()

# --- 6. LOGICA DI ACCESSO (LOGIN MANUALE) ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Gestionale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login Personale")
        st.info("Inserire COGNOME NOME (es. ROSSINI LORENZO)")
        nome_input = st.text_input("Nome e Cognome").strip().upper()
        pass_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if nome_input in df_dip['Nome'].str.upper().values:
                idx = df_dip[df_dip['Nome'].str.upper() == nome_input].index[0]
                u_row = df_dip.iloc[idx]
                pass_db = str(u_row['Password']).replace('.0', '').strip()
                
                if str(pass_input).strip() == pass_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    if str(u_row['PrimoAccesso']).upper() in ['TRUE', '1', 'SÌ']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password non corretta.")
            else:
                st.error("❌ Utente non trovato nel database.")
    
    else:
        st.subheader("🔒 Cambio Password Obbligatorio")
        st.warning("La tua password deve essere aggiornata per motivi di sicurezza.")
        n_p = st.text_input("Nuova Password", type="password")
        c_p = st.text_input("Conferma Password", type="password")
        if st.button("Aggiorna e Accedi"):
            if n_p == c_p and len(n_p) >= 5:
                idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato].tolist()[0]
                df_dip.at[idx, 'Password'] = n_p
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                conn.update(worksheet="Dipendenti", data=df_dip)
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")

else:
    # --- 7. AREA RISERVATA ---
    st.sidebar.title("Menu")
    st.sidebar.write(f"👤 Utente: **{st.session_state.utente_loggato}**")
    if st.sidebar.button("Esci"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Invia Richiesta", "Pannello Admin"]
    choice = st.sidebar.selectbox("Naviga", menu)

    if choice == "I miei Saldi":
        st.header("Visualizzazione Saldi")
        dati_u = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati_u[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Invia Richiesta":
        st.header("Nuova Richiesta Assenza")
        with st.form("form_richiesta"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL", "Permesso Visita", "Altro"])
            dal = st.date_input("Dalla data")
            al = st.date_input("Alla data")
            motivo = st.text_area("Note opzionali")
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {tipo}\nPeriodo: {dal} - {al}\nNote: {motivo}"
                if send_email(f"RICHIESTA {tipo.upper()} - {st.session_state.utente_loggato}", corpo):
                    st.success("✅ Email inviata correttamente!")
                    st.balloons()
                else:
                    st.error("❌ Errore tecnico nell'invio dell'email.")

    elif choice == "Pannello Admin":
        if "LORENZO" in st.session_state.utente_loggato.upper():
            st.header("🛠️ Strumenti Amministratore")
            st.dataframe(df_dip)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("➕ Aggiungi Risorsa")
                with st.expander("Apri Form"):
                    new_n = st.text_input("Cognome Nome").upper()
                    new_c = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
                    if st.button("Conferma Aggiunta"):
                        new_row = {"Nome": new_n, "Password": "12345", "Contratto": new_c, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                        df_dip = pd.concat([df_dip, pd.DataFrame([new_row])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=df_dip)
                        st.success(f"Aggiunto: {new_n}")
                        st.rerun()

            with col2:
                st.subheader("🗑️ Elimina Risorsa")
                with st.expander("Apri Form"):
                    n_del = st.text_input("Cognome Nome da eliminare").upper()
                    if st.button("Elimina Definitivamente"):
                        df_dip = df_dip[df_dip['Nome'] != n_del]
                        conn.update(worksheet="Dipendenti", data=df_dip)
                        st.warning(f"Rimosso: {n_del}")
                        st.rerun()

            st.divider()
            st.subheader("🔐 Reset Password")
            n_res = st.text_input("Inserisci nome per reset a '12345'").upper()
            if st.button("Esegui Reset"):
                if n_res in df_dip['Nome'].values:
                    idx = df_dip[df_dip['Nome'] == n_res].index[0]
                    df_dip.at[idx, 'Password'] = '12345'
                    df_dip.at[idx, 'PrimoAccesso'] = 'TRUE'
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.success(f"Password di {n_res} resettata!")
        else:
            st.error("⛔ Area riservata all'amministratore.")
