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

# --- 4. ACCESSO E SICUREZZA (VERSIONE OBBLIGATORIA) ---
if not st.session_state.autenticato:
    
    # FASE 2: SE IL LOGIN È OK MA DEVE CAMBIARE PASSWORD
    if st.session_state.cambio_obbligatorio:
        st.title("🔑 Cambio Password Obbligatorio")
        st.warning(f"Benvenuto {st.session_state.utente_loggato}. Prima di consultare i tuoi saldi, devi cambiare la password.")
        
        n_p = st.text_input("Inserisci Nuova Password (min. 5 car.)", type="password", key="new_p")
        c_p = st.text_input("Conferma Nuova Password", type="password", key="conf_p")
        
        if st.button("Salva Nuova Password"):
            if n_p == c_p and len(n_p) >= 5:
                # 1. Trova l'indice nel database
                idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                # 2. Aggiorna i dati sul DataFrame
                df_dip.at[idx, 'Password'] = n_p
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                # 3. Invia l'aggiornamento a Google Sheets
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                
                # 4. Sblocca l'accesso e resetta lo stato
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("✅ Password salvata! Ora puoi accedere.")
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")
        
        # BLOCCO DI SICUREZZA: se è in questa fase, NON può leggere altro
        st.stop()

    # FASE 1: LOGIN STANDARD
    st.title("🛡️ Accesso Portale BTV")
    u_scelto = st.selectbox("DIPENDENTE", ["--- Seleziona il tuo nome ---"] + sorted(df_dip['Nome_Display'].unique()))
    p_in = st.text_input("PASSWORD", type="password")
    
    if st.button("Verifica Credenziali"):
        if u_scelto != "--- Seleziona il tuo nome ---":
            idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
            row = df_dip.iloc[idx]
            pw_db = str(row['Password']).split('.')[0].strip()
            
            if str(p_in).strip() == pw_db:
                # Salviamo l'identità
                st.session_state.utente_loggato = str(row['Nome_Display'])
                
                # Verifichiamo se è il primo accesso (se TRUE -> Cambio obbligatorio)
                is_primo = str(row['PrimoAccesso']).strip().upper()
                if is_primo in ['1', '1.0', 'TRUE', 'SÌ', 'VERO']:
                    st.session_state.cambio_obbligatorio = True
                    # IMPORTANTE: NON mettiamo autenticato=True qui!
                    st.rerun()
                else:
                    # Se non è il primo accesso, entra normalmente
                    st.session_state.autenticato = True
                    st.rerun()
            else:
                st.error("❌ Password errata")
    
    # Impedisce la visualizzazione dei saldi a chi non ha superato i controlli sopra
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
        st.header("⚙️ Amministrazione")
        st.dataframe(df_dip.drop(columns=['Nome_Display']))
