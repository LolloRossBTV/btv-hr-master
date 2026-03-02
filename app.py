import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# --- 1. CONFIGURAZIONE DELLA PAGINA E DELLO STATO ---
st.set_page_config(page_title="Portale Gestionale BTV", layout="centered")

# Inizializzazione variabili di sessione per sicurezza e navigazione
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 2. FUNZIONE INVIO EMAIL (SMTP GMAIL) ---
def send_email(subject, body):
    try:
        # Recupero parametri dai Secrets
        creds = st.secrets["emails"]
        msg = MIMEMultipart()
        msg['From'] = creds["sender_email"]
        msg['To'] = creds["receiver_email"]
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Connessione al server SMTP
        server = smtplib.SMTP(creds["smtp_server"], int(creds["smtp_port"]))
        server.starttls()
        
        # Pulizia della password app (16 caratteri senza spazi)
        pwd_pulita = str(creds["sender_password"]).replace(" ", "").strip()
        
        server.login(creds["sender_email"], pwd_pulita)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Errore critico invio Email: {e}")
        return False

# --- 3. CONNESSIONE AL DATABASE GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Lettura senza cache per aggiornamento dati immediato
    df_dip = conn.read(worksheet="Dipendenti", ttl=0).dropna(subset=['Nome'])
    # Creazione colonna di confronto per evitare errori di formattazione
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.strip()
except Exception as e:
    st.error(f"❌ Errore di connessione al Database: {e}")
    st.stop()

# --- 4. LOGICA ACCESSO E SICUREZZA ---
if not st.session_state.autenticato:
    if st.session_state.cambio_obbligatorio:
        st.title("🔑 Cambio Password Obbligatorio")
        st.warning(f"Ciao {st.session_state.utente_loggato}, imposta una nuova password.")
        
        n_p = st.text_input("Nuova Password (min. 5 caratteri)", type="password")
        c_p = st.text_input("Conferma Nuova Password", type="password")
        
        if st.button("Salva e Accedi al Portale"):
            # CORRETTO: n_p invece di n_n
            if n_p == c_p and len(n_p) >= 5:
                idx_u = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_u, 'Password'] = n_p
                df_dip.at[idx_u, 'PrimoAccesso'] = 'FALSE'
                
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("✅ Password aggiornata!")
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")
        st.stop()

    st.title("🛡️ Accesso Portale BTV")
    nomi_lista = sorted(df_dip['Nome_Display'].unique())
    u_scelto = st.selectbox("DIPENDENTE", ["--- Seleziona ---"] + nomi_lista)
    p_in = st.text_input("PASSWORD", type="password")
    
    if st.button("Accedi"):
        if u_scelto != "--- Seleziona ---":
            idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
            row = df_dip.iloc[idx]
            pw_db = str(row['Password']).split('.')[0].strip()
            if str(p_in).strip() == pw_db:
                st.session_state.utente_loggato = row['Nome_Display']
                if str(row['PrimoAccesso']).strip().upper() in ['1', '1.0', 'TRUE', 'SÌ']:
                    st.session_state.cambio_obbligatorio = True
                    st.rerun()
                else:
                    st.session_state.autenticato = True
                    st.rerun()
            else:
                st.error("❌ Password errata.")
    # --- 5. INTERFACCIA UTENTE AUTENTICATO ---
    st.sidebar.success(f"👤 Utente: {st.session_state.utente_loggato}")
    
    opzioni = ["I miei Saldi", "Invia Richiesta"]
    # Controllo privilegi amministratore (basato sul cognome Rossini)
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        opzioni.append("Pannello Amministrazione")
    
    scelta_menu = st.sidebar.selectbox("Navigazione", opzioni)
    
    if st.sidebar.button("Logout / Esci"):
        st.session_state.autenticato = False
        st.rerun()

    # --- SEZIONE: I MIEI SALDI ---
    if scelta_menu == "I miei Saldi":
        st.header("Riepilogo Contatori Personali")
        info_u = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato]
        st.table(info_u[['Ferie', 'ROL', 'Contratto']])

    # --- SEZIONE: INVIA RICHIESTA (CON CALENDARIO) ---
    elif scelta_menu == "Invia Richiesta":
        st.header("Inoltro Nuova Richiesta")
        with st.form("modulo_richiesta_btv"):
            # Menu pulito come richiesto
            causale = st.selectbox("Seleziona Causale", [
                "Ferie", 
                "ROL (Permesso Orario)", 
                "Legge 104", 
                "Congedo Parentale"
            ])
            
            st.write("Seleziona il periodo desiderato:")
            date_input = st.date_input("Calendario", value=(), label_visibility="collapsed")
            
            note_testo = st.text_area("Note aggiuntive (obbligatorio per orari ROL o dettagli 104)")
            
            if st.form_submit_button("Invia ai Responsabili"):
                if len(date_input) >= 1:
                    if len(date_input) == 2:
                        testo_periodo = f"Dal {date_input[0]} al {date_input[1]}"
                    else:
                        testo_periodo = f"Giorno singolo: {date_input[0]}"
                    
                    corpo_email = f"""
                    NUOVA RICHIESTA PORTALE BTV
                    ---------------------------
                    Dipendente: {st.session_state.utente_loggato}
                    Causale: {causale}
                    Periodo: {testo_periodo}
                    Note: {note_testo}
                    """
                    
                    if send_email(f"RICHIESTA {causale.upper()} - {st.session_state.utente_loggato}", corpo_email):
                        st.success(f"✅ Richiesta inoltrata per: {testo_periodo}")
                        st.balloons()
                else:
                    st.error("⚠️ Attenzione: Seleziona almeno una data sul calendario!")

    # --- SEZIONE: PANNELLO AMMINISTRAZIONE ---
    elif scelta_menu == "Pannello Amministrazione":
        st.header("⚙️ Gestione Personale e Database")
        st.dataframe(df_dip.drop(columns=['Nome_Display']), use_container_width=True)
        
        st.divider()
        col_add, col_del = st.columns(2)
        
        with col_add:
            st.subheader("➕ Aggiungi Dipendente")
            nuovo_nome = st.text_input("Nome e Cognome (MAIUSCOLO)").upper().strip()
            tipo_contratto = st.selectbox("Contratto", ["Fiduciario", "Guardia"])
            if st.button("Registra Nuovo"):
                new_data = {"Nome": nuovo_nome, "Password": "12345", "Contratto": tipo_contratto, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_finale = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([new_data])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_finale)
                st.success(f"Utente {nuovo_nome} aggiunto!")
                st.rerun()
        
        with col_del:
            st.subheader("🗑️ Rimuovi Dipendente")
            lista_del = sorted(df_dip['Nome_Display'].unique())
            da_eliminare = st.selectbox("Seleziona profilo", lista_del)
            if st.button("Elimina Definitivamente"):
                df_ridotto = df_dip[df_dip['Nome_Display'] != da_eliminare].drop(columns=['Nome_Display'])
                conn.update(worksheet="Dipendenti", data=df_ridotto)
                st.warning(f"Profilo di {da_eliminare} rimosso.")
                st.rerun()
