import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. INIZIALIZZAZIONE STATO (Risolve AttributeError) ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 2. CONFIGURAZIONE & EMAIL ---
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
        st.error(f"Errore email: {e}")
        return False

# --- 3. CONNESSIONE DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_richieste = conn.read(worksheet="Richieste", ttl=0)
except Exception as e:
    st.error(f"⚠️ Errore di connessione: {e}")
    st.stop()

# --- 4. LOGICA DI ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("Benvenuto in BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Accesso Riservato")
        nome_utente = st.selectbox("Seleziona il tuo Nome", df_dip['Nome'].tolist())
        password_input = st.text_input("Password", type="password")
        
        if st.button("Accedi"):
            utente_row = df_dip.loc[df_dip['Nome'] == nome_utente]
            
            # Pulizia password e controllo PrimoAccesso (per Bozzi e altri)
            password_db = str(utente_row.iloc[0]['Password']).replace('.0', '').strip()
            valore_primo_acc = str(utente_row.iloc[0]['PrimoAccesso']).strip().upper()
            
            # Riconosce TRUE, VERO, SÌ, 1 o 1.0 (checkbox di Google)
            is_primo_accesso = valore_primo_acc in ['TRUE', 'SÌ', '1', 'VERO', '1.0']
            
            if str(password_input).strip() == password_db:
                st.session_state.utente_loggato = nome_utente
                if is_primo_accesso:
                    st.session_state.cambio_obbligatorio = True
                    st.rerun()
                else:
                    st.session_state.autenticato = True
                    st.rerun()
            else:
                st.error("❌ Password errata.")
    
    else:
        st.subheader("🔒 Cambio Password Obbligatorio")
        st.info(f"Ciao {st.session_state.utente_loggato}, imposta una nuova password.")
        new_pass = st.text_input("Nuova Password", type="password")
        confirm_pass = st.text_input("Conferma Password", type="password")
        
        if st.button("Salva e Accedi"):
            if new_pass == confirm_pass and len(new_pass) >= 5:
                # Trova riga e aggiorna
                idx = df_dip.index[df_dip['Nome'] == st.session_state.utente_loggato].tolist()[0]
                df_dip.at[idx, 'Password'] = new_pass
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE'
                
                try:
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.success("✅ Password aggiornata!")
                    st.session_state.cambio_obbligatorio = False
                    st.session_state.autenticato = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore salvataggio Google: {e}")
            else:
                st.error("❌ Password non valide (min. 5 car).")

else:
    # --- 5. INTERFACCIA UTENTI LOGGATI ---
    st.sidebar.success(f"Loggato: {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()

    menu = ["I miei Saldi", "Invia Richiesta", "Gestione Admin"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "I miei Saldi":
        st.header(f"Saldi di {st.session_state.utente_loggato}")
        dati_u = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
        st.table(dati_u[['Ferie', 'ROL']])

    elif choice == "Invia Richiesta":
        st.header("Compila la richiesta")
        st.info("Funzione in arrivo...")


elif choice == "Gestione Admin":
        # Controllo flessibile: trasforma tutto in maiuscolo per evitare errori
        utente_attuale = st.session_state.utente_loggato.upper()
        
        if "LORENZO" in utente_attuale and "ROSSINI" in utente_attuale:
            st.header("🛠️ Pannello di Controllo Admin")
            
            # Visualizzazione tabella generale
            st.subheader("Riepilogo Dipendenti")
            st.dataframe(df_dip)
            
            st.divider()
            
            # --- FUNZIONE RESET PASSWORD ---
            st.subheader("🔐 Reset Password Dipendente")
            st.write("Riporta la password a '12345' con obbligo di cambio.")
            
            # Seleziona il dipendente escludendo se stessi
            lista_dipendenti = [n for n in df_dip['Nome'].tolist() if "ROSSINI" not in n.upper()]
            dip_da_resettare = st.selectbox("Seleziona Dipendente", lista_dipendenti)
            
            if st.button("Esegui Reset Password"):
                idx_res = df_dip.index[df_dip['Nome'] == dip_da_resettare].tolist()[0]
                df_dip.at[idx_res, 'Password'] = '12345'
                df_dip.at[idx_res, 'PrimoAccesso'] = 'TRUE'
                
                try:
                    conn.update(worksheet="Dipendenti", data=df_dip)
                    st.success(f"✅ Reset completato per {dip_da_resettare}!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Errore: {e}")
        else:
            st.error(f"⛔ Accesso negato. Il sistema ti riconosce come '{st.session_state.utente_loggato}', che non ha permessi admin.")
