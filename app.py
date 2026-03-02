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
        st.error(f"❌ Errore Email (535): Password rifiutata da Google. {e}")
        return False

# --- 4. CARICAMENTO E PULIZIA DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    
    # Creiamo una colonna di match pulita per evitare l'errore 'Series object'
    # Questo risolve l'errore rosa che vedevi all'apertura
    df_dip['Match_Nome'] = df_dip['Nome'].astype(str).str.strip().str.upper()
    
    # Pulizia colonna PrimoAccesso per il check obbligatorio
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip().upper()
except Exception as e:
    st.error(f"❌ Errore critico nel caricamento del database: {e}")
    st.stop()

# --- 5. LOGICA ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("🛡️ Portale Gestionale BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Login Riservato")
        nome_in = st.text_input("Inserisci COGNOME NOME").strip().upper()
        pass_in = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            if nome_in in df_dip['Match_Nome'].values:
                idx = df_dip[df_dip['Match_Nome'] == nome_in].index[0]
                u_row = df_dip.iloc[idx]
                
                # Gestione password (rimuove .0 se il foglio Google la vede come numero)
                pw_db = str(u_row['Password']).split('.')[0].strip()
                
                if str(pass_in).strip() == pw_db:
                    st.session_state.utente_loggato = u_row['Nome']
                    
                    # --- CHECK OBBLIGO CAMBIO PASSWORD ---
                    # Se il valore è 1, 1.0, TRUE, VERO o SÌ, scatta l'obbligo
                    val_primo = str(u_row['PrimoAccesso']).strip()
                    if val_primo in ['1', '1.0', 'TRUE', 'VERO', 'SÌ']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password errata.")
            else:
                st.error("❌ Utente non trovato. Verifica lo spelling.")
    
    else:
        # --- SCHERMATA CAMBIO PASSWORD OBBLIGATORIO ---
        st.subheader("🔑 Primo Accesso: Imposta Password Personale")
        st.warning(f"Ciao {st.session_state.utente_loggato}, per la tua sicurezza devi cambiare la password predefinita.")
        new_p = st.text_input("Nuova Password (min. 5 caratteri)", type="password")
        conf_p = st.text_input("Conferma Password", type="password")
        
        if st.button("Salva e Accedi"):
            if new_p == conf_p and len(new_p) >= 5:
                # Trova l'indice corretto nel database originale
                idx_orig = df_dip[df_dip['Nome'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_orig, 'Password'] = new_p
                df_dip.at[idx_orig, 'PrimoAccesso'] = 'FALSE'
                
                # Rimuove la colonna di servizio prima di salvare su Google Sheets
                df_to_save = df_dip.drop(columns=['Match_Nome'])
                conn.update(worksheet="Dipendenti", data=df_to_save)
                
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("✅ Password aggiornata con successo!")
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")

else:
    # --- 6. INTERFACCIA PRINCIPALE ---
    st.sidebar.success(f"👤 Loggato: {st.session_state.utente_loggato}")
    if st.sidebar.button("Esci (Logout)"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Richiesta Ferie/ROL", "Area Admin"]
    choice = st.sidebar.selectbox("Seleziona sezione", menu)

    if choice == "I miei Saldi":
        st.header("Riepilogo Contatori Personali")
        dati = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati[['Ferie', 'ROL', 'Contratto']])

    elif choice == "Richiesta Ferie/ROL":
        st.header("Invia una nuova richiesta")
        with st.form("form_ferie"):
            tipo = st.selectbox("Tipo Assenza", ["Ferie", "ROL", "Permesso"])
            inizio = st.date_input("Dalla data")
            fine = st.date_input("Alla data")
            motivo = st.text_area("Note aggiuntive")
            if st.form_submit_button("Invia ai Responsabili"):
                corpo = f"Richiesta da: {st.session_state.utente_loggato}\nTipo: {tipo}\nPeriodo: {inizio} - {fine}\nNote: {motivo}"
                if send_email(f"RICHIESTA PORTALE - {st.session_state.utente_loggato}", corpo):
                    st.success("✅ Email inviata con successo!")
                    st.balloons()

    elif choice == "Area Admin":
        # Controllo se l'utente è Lorenzo Rossini
        u_log = st.session_state.utente_loggato.upper()
        if "LORENZO" in u_log and "ROSSINI" in u_log:
            st.header("🛠️ Strumenti Amministratore")
            st.dataframe(df_dip.drop(columns=['Match_Nome']))
            
            # --- AGGIUNGI DIPENDENTE ---
            st.divider()
            st.subheader("➕ Inserisci Nuova Risorsa")
            with st.expander("Apri modulo inserimento"):
                n_new = st.text_input("Cognome Nome").upper()
                c_new = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
                if st.button("Registra Dipendente"):
                    if n_new:
                        new_r = {"Nome": n_new, "Password": "12345", "Contratto": c_new, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                        # Pulizia prima del concat
                        df_ready = df_dip.drop(columns=['Match_Nome'])
                        df_final = pd.concat([df_ready, pd.DataFrame([new_r])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=df_final)
                        st.success(f"✅ {n_new} aggiunto correttamente.")
                        st.rerun()

            # --- ELIMINA DIPENDENTE ---
            st.divider()
            st.subheader("🗑️ Elimina Risorsa")
            with st.expander("Apri modulo rimozione"):
                n_del = st.text_input("Nome esatto da eliminare").upper()
                if st.button("CONFERMA RIMOZIONE DEFINITIVA"):
                    if n_del in df_dip['Nome'].values:
                        df_rem = df_dip[df_dip['Nome'] != n_del].drop(columns=['Match_Nome'])
                        conn.update(worksheet="Dipendenti", data=df_rem)
                        st.warning(f"🗑️ {n_del} rimosso dal database.")
                        st.rerun()

            # --- RESET PASSWORD ---
            st.divider()
            st.subheader("🔐 Reset Password Personale")
            u_res = st.selectbox("Seleziona dipendente per reset a 12345", df_dip['Nome'].values)
            if st.button("Esegui Reset Password"):
                idx_r = df_dip[df_dip['Nome'] == u_res].index[0]
                df_dip.at[idx_r, 'Password'] = '12345'
                df_dip.at[idx_r, 'PrimoAccesso'] = 'TRUE'
                df_save = df_dip.drop(columns=['Match_Nome'])
                conn.update(worksheet="Dipendenti", data=df_save)
                st.success(f"✅ Password di {u_res} riportata a 12345.")
        else:
            st.error("⛔ Accesso negato: questa sezione è riservata a Lorenzo Rossini.")
