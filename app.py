import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- CONFIGURAZIONE INIZIALE ---
st.set_page_config(page_title="Gestione Presenze BTV", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNZIONE INVIO E-MAIL ---
def invia_notifica_email(utente, tipo, periodo, note):
    # --- CONFIGURA QUI I TUOI DATI ---
    mittente = "rossini.lzo@gmail.com"  
    password = "spav pctg oolm cnps"   
    destinatario = "lorenzo.rossini@battistolli.it" 
    
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = destinatario
    msg['Subject'] = f"RICHIESTA ASSENZA: {utente} - {tipo}"
    corpo = f"Nuova richiesta inserita:\n\nDipendente: {utente}\nTipo: {tipo}\nPeriodo: {periodo}\nNote: {note}"
    msg.attach(MIMEText(corpo, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mittente, password)
        server.send_message(msg)
        server.quit()
        return True
    except:
        return False

# --- CARICAMENTO DATI ---
try:
    # ttl=0 forza la lettura immediata senza cache
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_dip.columns = df_dip.columns.str.strip()
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip()
except Exception as e:
    st.error(f"Errore database: {e}"); st.stop()

if "autenticato" not in st.session_state: st.session_state.autenticato = False
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None

st.title("🏥 Sistema Gestione Assenze BTV")

# --- 1. LOGICA LOGIN ---
if not st.session_state.autenticato:
    with st.form("login_form"):
        user = st.selectbox("Seleziona il tuo Nome", df_dip['Nome_Display'].tolist())
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRA"):
            val = df_dip[(df_dip['Nome_Display'] == user) & (df_dip['Password'].astype(str).str.strip() == str(pw).strip())]
            if not val.empty:
                st.session_state.autenticato = True
                st.session_state.utente_loggato = user
                st.rerun()
            else:
                st.error("Password errata!")

# --- 2. AREA RISERVATA ---
else:
    dati_u = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]

    # --- CONTROLLO CAMBIO PASSWORD OBBLIGATORIO ---
    if dati_u['PrimoAccesso'] == "1":
        st.header("🔑 Cambio Password Obbligatorio")
        st.warning(f"Ciao {st.session_state.utente_loggato}, devi impostare una nuova password per continuare.")
        with st.form("cambio_pw_form"):
            n_pw = st.text_input("Nuova Password", type="password")
            c_pw = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA E ACCEDI"):
                if n_pw == c_pw and len(n_pw) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = str(n_pw).strip()
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success("Password aggiornata!"); st.rerun()
                else:
                    st.error("Le password non coincidono o sono troppo brevi (min. 4 caratteri).")
        st.stop()

    # --- CARICAMENTO ALTRE TABELLE ---
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl="1m")
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
    except:
        df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    # --- SIDEBAR ---
    st.sidebar.success(f"👤 {st.session_state.utente_loggato}")
    menu = ["📊 Dashboard", "📩 Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        menu.append("⚙️ Admin")
    scelta = st.sidebar.radio("Navigazione", menu)
    
    if st.sidebar.button("Logout", key="btn_logout"):
        st.session_state.autenticato = False
        st.rerun()

    # --- SEZIONE DASHBOARD ---
    if scelta == "📊 Dashboard":
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{dati_u['Ferie']} gg")
        c2.metric("ROL residui", f"{dati_u['ROL']} ore")
        c3.metric("Contratto", dati_u['Contratto'])

    # --- SEZIONE INVIO RICHIESTA ---
    elif scelta == "📩 Invia Richiesta":
        with st.form("invio_richiesta"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL", "104", "Congedo Parentale", "Congedo Matrimoniale"])
            per = st.date_input("Periodo", value=())
            note = st.text_area("Note")
            if st.form_submit_button("Invia"):
                if len(per) == 2:
                    giorni = pd.date_range(start=per[0], end=per[1])
                    mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
                    possibile = True
                    for g in giorni:
                        m_n = mesi_it[g.month - 1]
                        lim_g = 3
                        if not df_limiti.empty:
                            r_l = df_limiti[df_limiti['Mese'].str.lower() == m_n.lower()]
                            if not r_l.empty: lim_g = int(r_l['Limite'].values[0])
                        occ = df_richieste[df_richieste['Periodo'].astype(str) == str(g.date())].shape[0]
                        if tipo in ["Ferie", "ROL"] and occ >= lim_g:
                            st.error(f"Giorno {g.date()} al completo (Max {lim_g})"); possibile = False; break
                    if possibile:
                        nuove = [{"Data_Richiesta": datetime.now().strftime("%d/%m/%Y"), "Nome": st.session_state.utente_loggato, "Tipo": tipo, "Periodo": str(gx.date()), "Note": note} for gx in giorni]
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True))
                        invia_notifica_email(st.session_state.utente_loggato, tipo, f"{per[0]} - {per[1]}", note)
                        st.success("Richiesta inviata!"); st.balloons()
                else: st.warning("Seleziona data inizio e fine.")

    # --- SEZIONE ADMIN ---
    elif scelta == "⚙️ Admin":
        t1, t2, t3, t4, t5 = st.tabs(["📅 MATRICE LUN-DOM", "🔢 LIMITI MENSILI", "➕ AGGIUNGI", "🗑️ ELIMINA", "📊 DB"])
        
        with t1: # Matrice
            oggi = datetime.now().date()
            lunedi = oggi - timedelta(days=oggi.weekday())
            settimana = [lunedi + timedelta(days=i) for i in range(7)]
            df_richieste['Data_Giorno'] = pd.to_datetime(df_richieste['Periodo']).dt.date
            assenti = df_richieste[df_richieste['Data_Giorno'].isin(settimana)]['Nome'].unique()
            if len(assenti) > 0:
                matrice = []
                for dip in sorted(assenti):
                    r = {"Dipendente": dip}
                    for g in settimana:
                        col = g.strftime('%a %d/%m')
                        m = df_richieste[(df_richieste['Nome'] == dip) & (df_richieste['Data_Giorno'] == g)]
                        r[col] = m['Tipo'].values[0] if not m.empty else "-"
                    matrice.append(r)
                st.dataframe(pd.DataFrame(matrice).set_index("Dipendente"), use_container_width=True)
            else: st.info("Tutti presenti questa settimana.")

        with t2: # Limiti
            if not df_limiti.empty:
                nuovi_l = {}
                c1, c2, c3 = st.columns(3)
                for i, r in df_limiti.iterrows():
                    with [c1, c2, c3][i % 3]:
                        nuovi_l[r['Mese']] = st.number_input(f"Limite {r['Mese']}", 1, 20, int(r['Limite']), key=f"lim_{r['Mese']}")
                if st.button("Salva Limiti"):
                    conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi_l.items()), columns=['Mese', 'Limite']))
                    st.success("Limiti aggiornati!"); st.rerun()

        with t3: # Aggiungi
            with st.form("add_form"):
                nn = st.text_input("Nome e Cognome").upper()
                cc = st.selectbox("Contratto", ["Fiduciario", "Armato", "Amministrativo"])
                if st.form_submit_button("Registra"):
                    nuovo = {"Nome": nn, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": cc, "PrimoAccesso": "1"}
                    conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True))
                    st.success(f"{nn} aggiunto!"); st.rerun()

        with t4: # Elimina
            st.subheader("Rimuovi Dipendente")
            da_el = st.selectbox("Seleziona chi eliminare", ["---"] + df_dip['Nome'].tolist())
            if st.button("ELIMINA DEFINITIVAMENTE", type="primary"):
                if da_el != "---":
                    df_up = df_dip[df_dip['Nome'] != da_el].drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_up)
                    st.success(f"{da_el} eliminato."); st.rerun()

        with t5: # Database
            st.dataframe(df_richieste, use_container_width=True)
