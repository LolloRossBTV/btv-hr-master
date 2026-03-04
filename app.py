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
# --- AREA PRIVATA ---
    else:
        nome_u = str(st.session_state.utente_loggato)
        st.sidebar.success(f"👤 {nome_u}")
        
        menu = ["📊 Dashboard Saldi", "📩 Invia Richiesta"]
        if "ROSSINI" in nome_u.upper(): menu.append("⚙️ Pannello Admin")
        
        scelta = st.sidebar.radio("Navigazione", menu)
        
        if st.sidebar.button("Esci / Logout"):
            st.session_state.autenticato = False; st.rerun()

        if "Saldi" in scelta:
            st.header("📊 La tua situazione")
            dati_u = df_dip[df_dip['Nome_Display'] == nome_u].iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Ferie", f"{dati_u['Ferie']} gg")
            c2.metric("ROL", f"{dati_u['ROL']} ore")
            c3.metric("Contratto", dati_u['Contratto'])

        elif "Richiesta" in scelta:
            st.header("📩 Inserisci una richiesta")
            try:
                df_richieste = conn.read(worksheet="Richieste", ttl=0)
                df_limiti = conn.read(worksheet="LimitiMensili", ttl=0)
                
                with st.form("form_invio", clear_on_submit=True):
                    tipo = st.selectbox("Causale", ["Ferie", "ROL", "Legge 104", "Congedo"])
                    data_s = st.date_input("Giorno", value=None)
                    note = st.text_area("Note")
                    
                    if st.form_submit_button("🚀 Verifica e Invia"):
                        if data_s:
                            mesi_it = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
                            nome_m = mesi_it[data_s.month - 1]
                            lim_max = int(df_limiti[df_limiti['Mese'] == nome_m]['Limite'].values[0])
                            
                            occupati = df_richieste[(df_richieste['Periodo'].astype(str) == str(data_s))].shape[0]
                            
                            if occupati >= lim_max:
                                st.error(f"❌ Limite di {lim_max} persone raggiunto!")
                            else:
                                nuova_r = pd.DataFrame([{"Data_Richiesta": pd.Timestamp.now().strftime("%d/%m/%Y"), "Nome": nome_u, "Tipo": tipo, "Periodo": str(data_s), "Note": note}])
                                conn.update(worksheet="Richieste", data=pd.concat([df_richieste, nuova_r], ignore_index=True))
                                st.success("✅ Richiesta Inviata!"); st.balloons()
                        else: st.error("Seleziona una data!")
            except Exception as e: st.error(f"⚠️ Errore fogli GSheets: {e}")

        elif "Admin" in scelta:
            st.header("⚙️ Pannello Amministratore")
            t_lim, t_pers, t_db = st.tabs(["📅 LIMITI MENSILI", "👥 PERSONALE", "📊 DATABASE"])
            
            with t_lim:
                st.subheader("Imposta Limiti Massimi")
                try:
                    df_lim = conn.read(worksheet="LimitiMensili", ttl=0)
                    nuovi_v = {}
                    cols = st.columns(3)
                    for i, mese in enumerate(df_lim['Mese'].tolist()):
                        curr = int(df_lim.loc[df_lim['Mese'] == mese, 'Limite'].values[0])
                        with cols[i % 3]:
                            nuovi_v[mese] = st.number_input(f"{mese}", 1, 10, curr, key=f"l_{mese}")
                    
                    if st.button("💾 SALVA TUTTI I LIMITI", type="primary", use_container_width=True):
                        df_up = pd.DataFrame(list(nuovi_v.items()), columns=['Mese', 'Limite'])
                        conn.update(worksheet="LimitiMensili", data=df_up)
                        st.success("✅ Salvati!"); st.rerun()
                except: st.error("Foglio 'LimitiMensili' non trovato su GSheets!")

            with t_pers:
                col_a, col_r = st.columns(2)
                with col_a:
                    st.write("**Aggiungi Dipendente**")
                    with st.form("add"):
                        n = st.text_input("Nome").upper()
                        if st.form_submit_button("Salva"):
                            nuovo = {"Nome": n, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": "Fiduciario", "PrimoAccesso": "1"}
                            conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True))
                            st.success("Aggiunto!"); st.rerun()
                with col_r:
                    st.write("**Elimina Dipendente**")
                    u_d = st.selectbox("Chi?", ["---"] + sorted(df_dip['Nome_Display'].unique()))
                    if st.button("ELIMINA"):
                        conn.update(worksheet="Dipendenti", data=df_dip[df_dip['Nome_Display'] != u_d].drop(columns=['Nome_Display']))
                        st.rerun()

            with t_db:
                st.dataframe(df_dip.drop(columns=['Nome_Display']), use_container_width=True)
