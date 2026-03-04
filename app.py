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
        try:
            df_richieste = conn.read(worksheet="Richieste", ttl=0)
            df_limiti = conn.read(worksheet="LimitiMensili", ttl=0)
        except:
            st.error("⚠️ Verifica i fogli 'Richieste' e 'LimitiMensili' su Google Sheets")
            st.stop()

        with st.form("form_richiesta", clear_on_submit=True):
            tipo = st.selectbox("Causale", ["Ferie", "ROL (Permesso Orario)", "Legge 104", "Congedo Parentale"])
            data_scelta = st.date_input("Seleziona Giorno", value=None)
            note = st.text_area("Note aggiuntive")
            
            if st.form_submit_button("Verifica e Invia"):
                if data_scelta:
                    mesi_it = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
                    nome_mese = mesi_it[data_scelta.month - 1]
                    riga_lim = df_limiti[df_limiti['Mese'] == nome_mese]
                    lim_max = int(riga_lim['Limite'].values[0]) if not riga_lim.empty else 3

                    occupati = df_richieste[
                        (df_richieste['Periodo'].astype(str) == str(data_scelta)) & 
                        (df_richieste['Tipo'].isin(["Ferie", "ROL (Permesso Orario)"]))
                    ].shape[0]

                    if tipo not in ["Legge 104", "Congedo Parentale"] and occupati >= lim_max:
                        st.error(f"❌ Limite di {lim_max} persone raggiunto per il giorno {data_scelta}.")
                    else:
                        nuova_r = pd.DataFrame([{"Data_Richiesta": pd.Timestamp.now().strftime("%d/%m/%Y"), "Nome": nome_u, "Tipo": tipo, "Periodo": str(data_scelta), "Note": note}])
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, nuova_r], ignore_index=True))
                        corpo_m = f"Dipendente: {nome_u}\nTipo: {tipo}\nGiorno: {data_scelta}\nNote: {note}"
                        if send_email(f"RICHIESTA {tipo.upper()} - {nome_u}", corpo_m):
                            st.success("✅ Richiesta Inviata!"); st.balloons()
                else:
                    st.error("⚠️ Seleziona una data!")

    elif scelta == "Pannello Admin":
        st.header("⚙️ Pannello Amministratore")
        t_lim, t_res, t_add, t_del, t_db = st.tabs(["📅 LIMITI", "🔄 RESET", "➕ NUOVO", "🗑️ ELIMINA", "📊 DB"])

        with t_lim:
            st.subheader("Configurazione Limiti")
            try:
                df_lim = conn.read(worksheet="LimitiMensili", ttl=0)
                nuovi_v = {}
                c1, c2, c3 = st.columns(3)
                for i, mese in enumerate(df_lim['Mese'].tolist()):
                    curr = int(df_lim.loc[df_lim['Mese'] == mese, 'Limite'].values[0])
                    with [c1, c2, c3][i % 3]:
                        nuovi_v[mese] = st.number_input(f"{mese}", 1, 10, curr, key=f"n_{mese}")
                if st.button("🚀 SALVA LIMITI", use_container_width=True):
                    df_up = pd.DataFrame(list(nuovi_v.items()), columns=['Mese', 'Limite'])
                    conn.update(worksheet="LimitiMensili", data=df_up)
                    st.success("Salvati!"); st.rerun()
            except: st.error("Errore foglio LimitiMensili")

        with t_res:
            u_res = st.selectbox("Reset password per:", sorted(df_dip['Nome_Display'].unique()))
            if st.button("Esegui Reset"):
                idx = df_dip[df_dip['Nome_Display'] == u_res].index[0]
                df_dip.at[idx, 'Password'] = "12345"; df_dip.at[idx, 'PrimoAccesso'] = "1"
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.success("Reset OK!"); st.rerun()

        with t_add:
            with st.form("add_u"):
                n = st.text_input("Nome").upper()
                c = st.selectbox("Contratto", ["Fiduciario", "Armato", "Amministrativo"])
                if st.form_submit_button("Salva"):
                    nuovo = {"Nome": n, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": c, "PrimoAccesso": "1"}
                    conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True))
                    st.success("Aggiunto!"); st.rerun()

        with t_del:
            u_del = st.selectbox("Elimina:", ["---"] + sorted(df_dip['Nome_Display'].unique()))
            if st.button("CONFERMA ELIMINAZIONE"):
                conn.update(worksheet="Dipendenti", data=df_dip[df_dip['Nome_Display'] != u_del].drop(columns=['Nome_Display']))
                st.rerun()

        with t_db:
            st.dataframe(df_dip.drop(columns=['Nome_Display']), use_container_width=True)
