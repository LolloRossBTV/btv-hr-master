import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Portale Gestionale BTV", layout="centered")

# Inizializzazione variabili di stato
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 2. MOTORE INVIO EMAIL ---
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
        st.error(f"❌ Errore Email (535): Verifica la Password App nei Secrets. {e}")
        return False

# --- 3. CARICAMENTO E PULIZIA DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Carichiamo i dati freschi dal foglio "Dipendenti"
    df_dip = conn.read(worksheet="Dipendenti", ttl=0).dropna(subset=['Nome'])
    # Creiamo una colonna pulita per il menu a tendina
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.strip()
except Exception as e:
    st.error(f"❌ Errore caricamento Database: {e}")
    st.stop()

# --- 4. LOGICA DI ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    st.title("🛡️ Accesso Riservato BTV")
    
    if not st.session_state.cambio_obbligatorio:
        st.subheader("Seleziona il tuo profilo")
        lista_nomi = sorted(df_dip['Nome_Display'].unique())
        u_scelto = st.selectbox("DIPENDENTE", ["Scegli il tuo nome..."] + lista_nomi)
        p_in = st.text_input("PASSWORD", type="password")
        
        if st.button("Accedi al Portale"):
            if u_scelto != "Scegli il tuo nome...":
                idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
                row = df_dip.iloc[idx]
                # Pulizia password da eventuali formati numerici di Excel
                pw_db = str(row['Password']).split('.')[0].strip()
                
                if str(p_in).strip() == pw_db:
                    st.session_state.utente_loggato = row['Nome_Display']
                    # Controllo Primo Accesso (TRUE/1)
                    p_acc = str(row['PrimoAccesso']).strip().upper()
                    if p_acc in ['1', '1.0', 'TRUE', 'SÌ', 'VERO']:
                        st.session_state.cambio_obbligatorio = True
                        st.rerun()
                    else:
                        st.session_state.autenticato = True
                        st.rerun()
                else:
                    st.error("❌ Password non corretta.")
            else:
                st.warning("⚠️ Per favore, seleziona il tuo nome dalla lista.")
    
    else:
        # --- SCHERMATA CAMBIO PASSWORD OBBLIGATORIO ---
        st.subheader("🔑 Primo Accesso: Imposta Nuova Password")
        st.info(f"Ciao {st.session_state.utente_loggato}, per la tua sicurezza devi cambiare la password predefinita.")
        n_p = st.text_input("Nuova Password (min. 5 caratteri)", type="password")
        c_p = st.text_input("Conferma Nuova Password", type="password")
        
        if st.button("Salva Password e Entra"):
            if n_p == c_p and len(n_p) >= 5:
                idx_o = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx_o, 'Password'] = n_p
                df_dip.at[idx_o, 'PrimoAccesso'] = 'FALSE'
                # Aggiornamento su Google Sheets
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.success("Password aggiornata con successo!")
                st.rerun()
            else:
                st.error("❌ Le password non coincidono o sono troppo brevi.")

else:
    # --- 5. INTERFACCIA UTENTE (SIDEBAR) ---
    st.sidebar.success(f"👤 Collegato: {st.session_state.utente_loggato}")
    
    menu = ["I miei Saldi", "Invia Richiesta"]
    # Accesso Admin per Lorenzo Rossini
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        menu.append("Pannello Amministrazione")
    
    choice = st.sidebar.selectbox("Cosa vuoi fare?", menu)
    
    if st.sidebar.button("Esci / Logout"):
        st.session_state.autenticato = False
        st.rerun()

    # --- 6. PAGINA: I MIEI SALDI ---
    if choice == "I miei Saldi":
        st.header("Situazione Ferie e ROL")
        u_row = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato]
        st.table(u_row[['Ferie', 'ROL', 'Contratto']])

    # --- 7. PAGINA: INVIA RICHIESTA (CON CALENDARIO E NUOVE VOCI) ---
    elif choice == "Invia Richiesta":
        st.header("Modulo di Richiesta Assenza")
        with st.form("form_richiesta_completo"):
            # Menu a tendina aggiornato con 104 e Congedi
            tipo_a = st.selectbox("Tipo di assenza", [
                "Ferie", 
                "ROL (Permesso Orario)", 
                "Legge 104", 
                "Congedo Parentale", 
                "Recupero Ore",
                "Malattia / Infortunio"
            ])
            
            st.write("Seleziona le date sul calendario (clicca inizio e fine periodo):")
            d_range = st.date_input("Periodo", value=(), label_visibility="collapsed")
            
            note_a = st.text_area("Note aggiuntive (obbligatorio indicare orari per i ROL o dettagli per 104)")
            
            if st.form_submit_button("Invia ai Responsabili"):
                if len(d_range) == 2:
                    periodo_testo = f"Dal {d_range[0]} al {d_range[1]}"
                elif len(d_range) == 1:
                    periodo_testo = f"Giorno singolo: {d_range[0]}"
                else:
                    st.error("⚠️ Devi selezionare almeno una data sul calendario!")
                    st.stop()
                
                messaggio = f"Dipendente: {st.session_state.utente_loggato}\nTipo: {tipo_a}\nPeriodo: {periodo_testo}\nNote: {note_a}"
                
                if send_email(f"RICHIESTA {tipo_a.upper()} - {st.session_state.utente_loggato}", messaggio):
                    st.success(f"Richiesta inviata per: {periodo_testo}")
                    st.balloons()

    # --- 8. PAGINA: AMMINISTRAZIONE ---
    elif choice == "Pannello Amministrazione":
        st.header("⚙️ Gestione Database Dipendenti")
        st.dataframe(df_dip.drop(columns=['Nome_Display']))
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("➕ Nuovo Dipendente")
            new_n = st.text_input("Nome e Cognome").upper().strip()
            new_c = st.selectbox("Contratto", ["Guardia", "Fiduciario"])
            if st.button("Salva nel Foglio"):
                nuovo = {"Nome": new_n, "Password": "12345", "Contratto": new_c, "Ferie": 0, "ROL": 0, "PrimoAccesso": "TRUE"}
                df_upd = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True)
                conn.update(worksheet="Dipendenti", data=df_upd)
                st.success("Aggiunto!")
                st.rerun()
        
        with c2:
            st.subheader("🗑️ Elimina")
            # Lista aggiornata dinamicamente per l'eliminazione
            lista_del = sorted(df_dip['Nome_Display'].unique())
            del_n = st.selectbox("Chi vuoi rimuovere?", lista_del)
            if st.button("Elimina Definitivamente"):
                df_rem = df_dip[df_dip['Nome_Display'] != del_n].drop(columns=['Nome_Display'])
                conn.update(worksheet="Dipendenti", data=df_rem)
                st.warning(f"Utente {del_n} rimosso.")
                st.rerun()
