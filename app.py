import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE PAGINA E PARAMETRI ---
st.set_page_config(page_title="Portale Gestionale BTV", layout="centered")

# Valori maturazione (per eventuali calcoli futuri)
MAT_FERIE_GUARDIA = 1.83
MAT_FERIE_FIDUCIARIO = 1.50

# --- 2. INIZIALIZZAZIONE SESSIONE ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 3. MOTORE INVIO EMAIL ---
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
        st.error(f"❌ Errore critico Email: Verificare 'Password per le app' nei Secrets. (Dettaglio: {e})")
        return False

# --- 4. CARICAMENTO E PULIZIA DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Lettura senza cache per avere dati sempre freschi
    df_dip = conn.read(worksheet="Dipendenti", ttl=0).dropna(subset=['Nome'])
    
    # RISOLUZIONE DEFINITIVA ERRORE 'SERIES' (Screenshot rosa)
    # Trasformiamo preventivamente tutta la colonna in stringhe pulite
    df_dip['Match_Nome'] = df_dip['Nome'].astype(str).str.strip().str.upper()
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip().upper()
except Exception as e:
    st.error(f"❌ Errore caricamento Database: {e}")
    st.stop()

# --- 5. LOGICA ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Personale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login Riservato")
        u_in = st.text_input("COGNOME NOME").strip().upper()
        p_in = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if u_in in df_dip['Match_Nome'].values:
                idx = df_dip[df_dip['Match_Nome'] == u_in].index[0]
                row = df_dip.iloc[idx]
                
                # Pulizia password da eventuali decimali (es. 12345.0)
                pw_db = str(row['Password']).split('.')[0].strip()
                
                if str(p_in).strip() == pw_db:
                    st.session_state.utente_loggato = row['Nome']
                    # Controllo primo accesso (se PrimoAccesso è TRUE, 1 o SÌ)
                    if str(row['PrimoAccesso']) in ['1', '1.0', 'TRUE', 'SÌ', 'VERO']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password non corretta.")
            else:
                st.error("❌ Utente non trovato. Inserire COGNOME e NOME.")
    
    else:
        # --- SCHERMATA CAMBIO PASSWORD OBBLIGATORIO ---
        st.subheader("🔑 Primo Accesso: Cambio Password")
        st.info(f"Ciao {st.session_state.utente_loggato}, devi impostare una password personale per proseguire.")
        n_p = st.text_input("Nuova Password (min. 5 caratt.)", type="password")
        c_p = st.text_input("Conferma Nuova Password", type="password")
        
        if st.button("Aggiorna Password e Accedi"):
            if n_p == c_p and len(n_p) >= 5:
                idx_orig = df_dip[df_dip['Nome'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_orig, 'Password'] = n_p
                df_dip.at[idx_orig, 'PrimoAccesso'] = 'FALSE'
                
                # Aggiornamento foglio Google
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Match_Nome']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("Password aggiornata!")
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")

else:
    # --- 6. INTERFACCIA PRINCIPALE (SIDEBAR E NAVIGAZIONE) ---
    st.sidebar.success(f"👤 Utente: {st.session_state.utente_loggato}")
    
    menu = ["I miei Saldi", "Invia Richiesta"]
    # Accesso Admin basato sul nome
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        menu.append("Pannello Admin")
    
    choice = st.sidebar.selectbox("Seleziona operazione", menu)
    
    if st.sidebar.button("Log-out"):
        st.session_state.autenticato = False
        st.session_state.utente_loggato = None
        st.rerun()

    # --- 7. PAGINA: I MIEI SALDI ---
    if choice == "I miei Saldi":
        st.header("Riepilogo Contatori Personali")
        # Visualizzazione tabella filtrata per l'utente
        dati_u = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati_u[['Ferie', 'ROL', 'Contratto']])

    # --- 8. PAGINA: INVIA RICHIESTA ---
    elif choice == "Invia Richiesta":
        st.header("Compila la tua Richiesta")
        with st.form("form_richiesta"):
            tipo = st.selectbox("Cosa desideri richiedere?", ["Ferie", "ROL", "Permesso Straordinario"])
            note = st.text_area("Indica date, orari e eventuali motivazioni")
            
            if st.form_submit_button("Invia Richiesta"):
                corpo_mail = f"Richiesta inoltrata da: {st.session_state.utente_loggato}\nTipo: {tipo}\nNote: {note}"
                if send_email(f"RICHIESTA PORTALE - {st.session_state.utente_loggato}", corpo_mail):
                    st.success("✅ La tua richiesta è stata inviata correttamente via email.")
                    st.balloons()

    # --- 9. PAGINA: PANNELLO ADMIN ---
    elif choice == "Pannello Admin":
        st.header("⚙️ Gestione Personale BTV")
        # Mostra tabella completa
        st.dataframe(df_dip.drop(columns=['Match_Nome']))
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("➕ Aggiungi Dipendente")
            n_n = st.text_input("Nome e Cognome").upper()
            c_n = st.selectbox("Tipo Contratto", ["Guardia", "Fiduciario"])
            if st.button("Salva nel Database"):
                new_row = {"Nome": n_n, "Password": "12345", "Contratto": c_n, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_upd = pd.concat([df_dip.drop(columns=['Match_Nome']), pd.DataFrame([new_row])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_upd)
                st.success("Dipendente aggiunto!")
                st.rerun()
                
        with col2:
            st.subheader("🗑️ Rimuovi Dipendente")
            n_d = st.text_input("Inserisci nome esatto da eliminare").upper()
            if st.button("Elimina Definitivamente"):
                df_rem = df_dip[df_dip['Nome'] != n_d].drop(columns=['Match_Nome'])
                conn.update(worksheet="Dipendenti", data=df_rem)
                st.warning(f"Utente {n_d} rimosso.")
                st.rerun()

        st.divider()
        st.subheader("🔐 Reset Password")
        u_r = st.selectbox("Seleziona utente per il reset", df_dip['Nome'].values)
        if st.button("Resetta a '12345'"):
            idx_r = df_dip[df_dip['Nome'] == u_r].index[0]
            df_dip.at[idx_r, 'Password'] = '12345'
            df_dip.at[idx_r, 'PrimoAccesso'] = 'TRUE'
            conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Match_Nome']))
            st.success(f"Password per {u_r} resettata.")
