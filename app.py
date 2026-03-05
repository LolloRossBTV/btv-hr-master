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
  # --- 5. AREA PRIVATA (Sostituisci tutto da qui alla fine del file) ---
    else:
        nome_u = str(st.session_state.utente_loggato)
        dati_u = df_dip[df_dip['Nome_Display'] == nome_u].iloc[0]
        
        # --- BLOCCO CAMBIO PASSWORD OBBLIGATORIO ---
        if str(dati_u['PrimoAccesso']) == "1":
            st.warning(f"👋 Ciao {nome_u}, per sicurezza cambia la password al primo accesso.")
            with st.form("cambio_pass_obbligatorio"):
                nuova_p = st.text_input("Inserisci Nuova Password", type="password")
                conferma_p = st.text_input("Conferma Nuova Password", type="password")
                if st.form_submit_button("SALVA E ACCEDI"):
                    if nuova_p == conferma_p and len(nuova_p) > 3:
                        idx = df_dip[df_dip['Nome_Display'] == nome_u].index[0]
                        df_dip.at[idx, 'Password'] = nuova_p
                        df_dip.at[idx, 'PrimoAccesso'] = "0"
                        conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                        st.success("✅ Password aggiornata! Ora puoi usare l'app."); st.rerun()
                    else:
                        st.error("Le password non coincidono o sono troppo corte.")
            st.stop() 

        # --- CARICAMENTO DATI E MENU ---
        st.sidebar.success(f"👤 {nome_u}")
        try:
            # ttl="1m" evita l'errore "Quota Exceeded" che abbiamo visto nelle foto
            df_richieste = conn.read(worksheet="Richieste", ttl="1m")
            df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
        except:
            st.error("⚠️ Errore Database (Quota Google raggiunta). Attendi un minuto."); st.stop()

        menu = ["📊 Dashboard Saldi", "📩 Invia Richiesta"]
        if "ROSSINI" in nome_u.upper(): 
            menu.append("⚙️ Pannello Admin")
        
        scelta = st.sidebar.radio("Navigazione", menu)
        
        if st.sidebar.button("Logout"):
            st.session_state.autenticato = False; st.rerun()

        # 1. SEZIONE SALDI
        if scelta == "📊 Dashboard Saldi":
            st.header("📊 La tua situazione")
            c1, c2, c3 = st.columns(3)
            c1.metric("Ferie residue", f"{dati_u['Ferie']} gg")
            c2.metric("ROL residui", f"{dati_u['ROL']} ore")
            c3.metric("Contratto", dati_u['Contratto'])

        # 2. SEZIONE INVIO RICHIESTA (DAL/AL)
        elif scelta == "📩 Invia Richiesta":
            st.header("📩 Inserisci Richiesta Periodo")
            with st.form("form_periodo", clear_on_submit=True):
                tipo = st.selectbox("Causale", ["Ferie", "ROL", "Legge 104"])
                periodo_scelto = st.date_input("Seleziona periodo (Inizio e Fine)", value=())
                note = st.text_area("Note aggiuntive")
                if st.form_submit_button("🚀 Verifica e Invia"):
                    if len(periodo_scelto) == 2:
                        d_ini, d_fine = periodo_scelto
                        giorni = pd.date_range(start=d_ini, end=d_fine)
                        mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
                        
                        errore_limite = False
                        for g in giorni:
                            m_nome = mesi_it[g.month - 1]
                            lim = int(df_limiti[df_limiti['Mese'] == m_nome]['Limite'].values[0])
                            occ = df_richieste[df_richieste['Periodo'].astype(str) == str(g.date())].shape[0]
                            if tipo in ["Ferie", "ROL"] and occ >= lim:
                                errore_limite = True; st.error(f"❌ {g.strftime('%d/%m')} pieno!"); break
                        
                        if not errore_limite:
                            nuove = [{"Data_Richiesta": pd.Timestamp.now().strftime("%d/%m/%Y"), "Nome": nome_u, "Tipo": tipo, "Periodo": str(gx.date()), "Note": note} for gx in giorni]
                            conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True))
                            st.success("✅ Richiesta salvata!"); st.balloons()
                    else: st.warning("Seleziona Inizio e Fine nel calendario.")

        # 3. PANNELLO ADMIN INTEGRALE
        elif "Admin" in scelta:
            st.header("⚙️ Amministrazione")
            t_ods, t_lim, t_add, t_db = st.tabs(["📅 MATRICE ODS", "🔢 LIMITI", "➕ NUOVO", "📊 DB"])

            with t_ods:
                st.subheader("🗓️ Prospetto Assenze (7 giorni)")
                oggi = pd.Timestamp.now().date()
                giorni_p = [oggi + pd.Timedelta(days=i) for i in range(7)]
                df_richieste['Data_Giorno'] = pd.to_datetime(df_richieste['Periodo']).dt.date
                assenti = df_richieste[df_richieste['Data_Giorno'].isin(giorni_p)]['Nome'].unique()
                if len(assenti) > 0:
                    matrice = []
                    for dip in sorted(assenti):
                        r = {"Dipendente": dip}
                        for g in giorni_p:
                            col = g.strftime('%a %d/%m')
                            m = df_richieste[(df_richieste['Nome'] == dip) & (df_richieste['Data_Giorno'] == g)]
                            r[col] = m['Tipo'].values[0] if not m.empty else "-"
                        matrice.append(r)
                    st.dataframe(pd.DataFrame(matrice).set_index("Dipendente"), use_container_width=True)
                else: st.info("Tutti presenti!")

            with t_lim:
                nuovi_v = {}
                c1, c2, c3 = st.columns(3)
                for i, riga in df_limiti.iterrows():
                    m = riga['Mese']
                    with [c1, c2, c3][i % 3]:
                        nuovi_v[m] = st.number_input(f"{m.capitalize()}", 1, 15, int(riga['Limite']), key=f"l_{m}")
                if st.button("💾 AGGIORNA LIMITI", type="primary"):
                    conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi_v.items()), columns=['Mese', 'Limite']))
                    st.success("Fatto!"); st.rerun()

            with t_add:
                with st.form("f_add"):
                    nn = st.text_input("Nome e Cognome").upper()
                    cc = st.selectbox("Contratto", ["Fiduciario", "Armato", "Amministrativo"])
                    if st.form_submit_button("REGISTRA"):
                        nuovo = {"Nome": nn, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": cc, "PrimoAccesso": "1"}
                        conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True))
                        st.success("Aggiunto!"); st.rerun()

            with t_db:
                st.dataframe(df_richieste, use_container_width=True)
