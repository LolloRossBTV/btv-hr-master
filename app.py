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
        st.header("📩 Modulo Invio Richiesta")
        
        # Carichiamo i dati per il controllo (Assicurati che i fogli esistano su GSheets)
        try:
            df_richieste = conn.read(worksheet="Richieste", ttl=0)
            df_limiti = conn.read(worksheet="LimitiMensili", ttl=0)
        except:
            st.error("⚠️ Errore: Verifica che esistano i fogli 'Richieste' e 'LimitiMensili' su Google Sheets")
            st.stop()

        with st.form("form_richiesta", clear_on_submit=True):
            tipo = st.selectbox("Causale", ["Ferie", "ROL (Permesso Orario)", "Legge 104", "Congedo Parentale"])
            data_scelta = st.date_input("Seleziona Giorno", value=None)
            note = st.text_area("Note aggiuntive")
            
            if st.form_submit_button("Verifica e Invia"):
                if data_scelta:
                    # 1. Recupero Limite del Mese dal foglio LimitiMensili
                    mesi_it = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
                    nome_mese = mesi_it[data_scelta.month - 1]
                    riga_lim = df_limiti[df_limiti['Mese'] == nome_mese]
                    limite_max = int(riga_lim['Limite'].values[0]) if not riga_lim.empty else 3

                    # 2. Conteggio persone già prenotate per quel giorno (solo Ferie/ROL)
                    occupati = df_richieste[
                        (df_richieste['Periodo'].astype(str) == str(data_scelta)) & 
                        (df_richieste['Tipo'].isin(["Ferie", "ROL (Permesso Orario)"]))
                    ].shape[0]

                    # 3. Logica di blocco (eccezione per 104 e Congedi)
                    is_tutelata = tipo in ["Legge 104", "Congedo Parentale"]

                    if not is_tutelata and occupati >= limite_max:
                        st.error("❌ **Richiesta non accordata**")
                        st.warning(f"Spiacente, per il giorno {data_scelta} sono già presenti {occupati} richieste.")
                    else:
                        # REGISTRAZIONE SU GOOGLE SHEETS
                        nuova_r = pd.DataFrame([{
                            "Data_Richiesta": pd.Timestamp.now().strftime("%d/%m/%Y"),
                            "Nome": nome_u,
                            "Tipo": tipo,
                            "Periodo": str(data_scelta),
                            "Note": note
                        }])
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, nuova_r], ignore_index=True))
                        
                        # INVIO EMAIL
                        corpo_mail = f"Dipendente: {nome_u}\nTipo: {tipo}\nGiorno: {data_scelta}\nNote: {note}"
                        if send_email(f"RICHIESTA {tipo.upper()} - {nome_u}", corpo_mail):
                            st.success("✅ Richiesta Accordata e Inviata!")
                            st.balloons()
                else:
                    st.error("⚠️ Seleziona una data!")
    elif scelta == "Pannello Admin":
        st.header("⚙️ Pannello di Controllo Amministratore")

        # --- 1. FUNZIONE DI RICERCA / INTERROGAZIONE SALDI ---
        st.subheader("🔍 Interroga Saldi Dipendente")
        u_search = st.selectbox("Seleziona una risorsa per visualizzare i dettagli", 
                                ["--- Seleziona ---"] + sorted(df_dip['Nome_Display'].unique()))
        
        if u_search != "--- Seleziona ---":
            dati_u = df_dip[df_dip['Nome_Display'] == u_search].iloc[0]
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Ferie Residue", f"{dati_u['Ferie']} gg")
            with c2:
                st.metric("ROL Residui", f"{dati_u['ROL']} ore")
            with c3:
                st.metric("Contratto", dati_u['Contratto'])
            
            st.divider()

        # --- 2. GESTIONE OPERATIVA (Al posto della tabella) ---
        tabs = st.tabs(["🔄 Reset Password", "➕ Nuova Risorsa", "🗑️ Elimina Risorsa", "📊 Tabella Completa"])

        with tabs[0]: # RESET
            st.write("Riporta la password di un dipendente a '12345' e forza il cambio al primo accesso.")
            u_res = st.selectbox("Dipendente da resettare", sorted(df_dip['Nome_Display'].unique()), key="res_admin")
            if st.button("Esegui Reset Ora"):
                idx = df_dip[df_dip['Nome_Display'] == u_res].index[0]
                df_dip.at[idx, 'Password'] = "12345"
                df_dip.at[idx, 'PrimoAccesso'] = "1"
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.success(f"✅ Reset completato per {u_res}")
                st.rerun()

        with tabs[1]: # AGGIUNGI
            with st.form("add_user"):
                n_nome = st.text_input("Nome e Cognome").upper()
                col_a, col_b = st.columns(2)
                with col_a:
                    n_contratto = st.selectbox("Tipo Contratto", ["Fiduciario", "Armato", "Amministrativo"])
                    n_ferie = st.number_input("Ferie", value=0)
                with col_b:
                    n_rol = st.number_input("ROL", value=0)
                if st.form_submit_button("Salva nel Database"):
                    if n_nome:
                        nuovo_rigo = {"Nome": n_nome, "Password": "12345", "Ferie": n_ferie, "ROL": n_rol, "Contratto": n_contratto, "PrimoAccesso": "1"}
                        df_nuovo = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo_rigo])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=df_nuovo)
                        st.success(f"✅ {n_nome} aggiunto!")
                        st.rerun()

        with tabs[2]: # ELIMINA
            u_del = st.selectbox("Rimuovi dipendente", ["---"] + sorted(df_dip['Nome_Display'].unique()), key="del_admin")
            if st.button("Elimina Definitivamente", type="primary"):
                if u_del != "---":
                    df_final = df_dip[df_dip['Nome_Display'] != u_del].drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_final)
                    st.warning(f"Rimosso {u_del}")
                    st.rerun()

        with tabs[3]: # TABELLA (Nascosta di default)
            st.write("Visualizzazione rapida di tutto il database:")
            st.dataframe(df_dip.drop(columns=['Nome_Display']), use_container_width=True)
