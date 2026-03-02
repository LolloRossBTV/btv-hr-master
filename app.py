import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# --- 1. CONFIGURAZIONE GENERALE DELL'INTERFACCIA ---
st.set_page_config(page_title="Portale Gestionale BTV", layout="centered")

# Inizializzazione degli stati della sessione per mantenere l'accesso
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 2. MOTORE INVIO EMAIL (SMTP GMAIL) ---
def send_email(subject, body):
    try:
        # Recupero credenziali dai Secrets di Streamlit
        creds = st.secrets["emails"]
        msg = MIMEMultipart()
        msg['From'] = creds["sender_email"]
        msg['To'] = creds["receiver_email"]
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Connessione al server SMTP di Google
        server = smtplib.SMTP(creds["smtp_server"], creds["smtp_port"])
        server.starttls() # Sicurezza necessaria
        # ATTENZIONE: Qui serve la "Password per le app" di 16 lettere
        server.login(creds["sender_email"], creds["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Errore Email (535): La password nei Secrets non è corretta. {e}")
        return False

# --- 3. CONNESSIONE E CARICAMENTO DATI DA GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Lettura del database con bypass della cache per dati in tempo reale
    df_dip = conn.read(worksheet="Dipendenti", ttl=0).dropna(subset=['Nome'])
    # Creazione di una colonna per il menu a tendina senza spazi extra
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.strip()
except Exception as e:
    st.error(f"❌ Impossibile collegarsi al database Google: {e}")
    st.stop()

# --- 4. LOGICA DI AUTENTICAZIONE ---
if not st.session_state.autenticato:
    st.title("🛡️ Accesso Portale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Seleziona il tuo nome dalla lista")
        nomi_puliti = sorted(df_dip['Nome_Display'].unique())
        u_scelto = st.selectbox("DIPENDENTE", ["--- Seleziona ---"] + nomi_puliti)
        p_in = st.text_input("PASSWORD", type="password")
        
        if st.button("Entra"):
            if u_scelto != "--- Seleziona ---":
                idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
                row = df_dip.iloc[idx]
                # Gestione password (rimozione .0 se Excel la legge come numero)
                pw_db = str(row['Password']).split('.')[0].strip()
                
                if str(p_in).strip() == pw_db:
                    st.session_state.utente_loggato = row['Nome_Display']
                    # Verifica se è il primo accesso per forzare il cambio password
                    primo_acc = str(row['PrimoAccesso']).strip().upper()
                    if primo_acc in ['1', '1.0', 'TRUE', 'SÌ', 'VERO']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password non corretta. Riprova.")
            else:
                st.warning("⚠️ Scegli prima il tuo nome.")
    
    else:
        # --- SCHERMATA CAMBIO PASSWORD ---
        st.subheader("🔑 Cambio Password Obbligatorio")
        st.info(f"Ciao {st.session_state.utente_loggato}, imposta una password sicura.")
        n_p = st.text_input("Nuova Password", type="password")
        c_p = st.text_input("Conferma Password", type="password")
        
        if st.button("Aggiorna Password"):
            if n_p == c_p and len(n_p) >= 5:
                idx_o = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_o, 'Password'] = n_p
                df_dip.at[idx_o, 'PrimoAccesso'] = 'FALSE'
                # Salvataggio su Google Sheets
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("Password salvata!")
                st.rerun()
            else:
                st.error("❌ Le password non corrispondono o sono troppo corte.")

else:
    # --- 5. AREA RISERVATA (LOGGED IN) ---
    st.sidebar.success(f"👤 Utente: {st.session_state.utente_loggato}")
    
    opzioni_menu = ["I miei Saldi", "Invia Richiesta"]
    # Controllo privilegi amministratore (per Lorenzo Rossini)
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        opzioni_menu.append("Pannello Admin")
    
    scelta = st.sidebar.selectbox("Cosa vuoi fare?", opzioni_menu)
    
    if st.sidebar.button("Log-out"):
        st.session_state.autenticato = False
        st.rerun()

    # --- PAGINA SALDI ---
    if scelta == "I miei Saldi":
        st.header("I tuoi Saldi Disponibili")
        riga_u = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato]
        st.table(riga_u[['Ferie', 'ROL', 'Contratto']])

    # --- PAGINA RICHIESTE (CON CALENDARIO E VOCI AGGIORNATE) ---
    elif scelta == "Invia Richiesta":
        st.header("Compila la tua Richiesta")
        with st.form("form_richiesta_finale"):
            # AGGIORNAMENTO: Inserite voci 104 e Congedi
            tipo_richiesta = st.selectbox("Tipo di assenza", [
                "Ferie", 
                "ROL (Permesso Orario)", 
                "Legge 104", 
                "Congedo Parentale", 
                "Recupero Ore", 
                "Malattia / Infortunio"
            ])
            
            st.write("Seleziona il periodo sul calendario:")
            periodo_scelto = st.date_input("Date", value=(), label_visibility="collapsed")
            
            dettagli = st.text_area("Note (Obbligatorio per orari ROL o dettagli 104)")
            
            if st.form_submit_button("Invia Richiesta"):
                if len(periodo_scelto) == 2:
                    testo_date = f"Dal {periodo_scelto[0]} al {periodo_scelto[1]}"
                elif len(periodo_scelto) == 1:
                    testo_date = f"Giorno singolo: {periodo_scelto[0]}"
                else:
                    st.error("⚠️ Seleziona almeno una data sul calendario!")
                    st.stop()
                
                corpo_mail = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {tipo_richiesta}\nPeriodo: {testo_date}\nNote: {dettagli}"
                
                if send_email(f"RICHIESTA {tipo_richiesta.upper()} - {st.session_state.utente_loggato}", corpo_mail):
                    st.success(f"✅ Inviata correttamente per: {testo_date}")
                    st.balloons()

    # --- PAGINA AMMINISTRAZIONE ---
    elif scelta == "Pannello Admin":
        st.header("⚙️ Gestione Database BTV")
        st.dataframe(df_dip.drop(columns=['Nome_Display']))
        
        st.divider()
        col_sx, col_dx = st.columns(2)
        
        with col_sx:
            st.subheader("➕ Aggiungi Dipendente")
            nome_n = st.text_input("Nome e Cognome").upper().strip()
            cont_n = st.selectbox("Tipo Contratto", ["Fiduciario", "Guardia"])
            if st.button("Salva Dipendente"):
                nuovo_d = {"Nome": nome_n, "Password": "12345", "Contratto": cont_n, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_nuovo = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo_d])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_nuovo)
                st.success("Aggiunto!")
                st.rerun()
        
        with col_dx:
            st.subheader("🗑️ Rimuovi Dipendente")
            lista_eliminazione = sorted(df_dip['Nome_Display'].unique())
            nome_d = st.selectbox("Seleziona chi eliminare", lista_eliminazione)
            if st.button("Elimina"):
                df_tagliato = df_dip[df_dip['Nome_Display'] != nome_d].drop(columns=['Nome_Display'])
                conn.update(worksheet="Dipendenti", data=df_tagliato)
                st.warning(f"Rimosso {nome_d}")
                st.rerun()
