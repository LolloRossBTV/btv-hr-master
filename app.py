import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="BTV Gestione Assenze", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNZIONE MAIL ---
def invia_notifica_email(utente, tipo, periodo, note):
    mittente = "tua_email@gmail.com"  
    password = "la_tua_app_password"   
    destinatario = "ufficio_personale@esempio.it" 
    msg = MIMEText(f"Richiesta da: {utente}\nTipo: {tipo}\nPeriodo: {periodo}\nNote: {note}")
    msg['Subject'] = f"RICHIESTA: {utente} - {tipo}"
    msg['From'] = mittente; msg['To'] = destinatario
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
        server.login(mittente, password); server.send_message(msg); server.quit()
        return True
    except: return False

# --- CARICAMENTO DATI ---
try:
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_dip.columns = df_dip.columns.str.strip()
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip()
except:
    st.error("Errore database."); st.stop()

if "autenticato" not in st.session_state: st.session_state.autenticato = False
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None

st.title("🏥 Sistema Gestione Assenze BTV")

# --- LOGICA ACCESSO ---
if not st.session_state.autenticato:
    with st.form("login_form"):
        user = st.selectbox("Seleziona Nome", df_dip['Nome_Display'].tolist())
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRA"):
            val = df_dip[(df_dip['Nome_Display'] == user) & (df_dip['Password'].astype(str).str.strip() == str(pw).strip())]
            if not val.empty:
                st.session_state.autenticato = True
                st.session_state.utente_loggato = user; st.rerun()
            else: st.error("Password errata!")

else:
    # 1. Recupero dati utente loggato
    utente_row = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]
    
    # 2. CONTROLLO CAMBIO PW (BLOCCO TOTALE)
    if str(utente_row['PrimoAccesso']) == "1":
        st.header("🔑 CAMBIO PASSWORD OBBLIGATORIO")
        st.warning(f"Benvenuto {st.session_state.utente_loggato}. Devi impostare una password personale per continuare.")
        with st.form("pw_obbligatorio"):
            n_pw = st.text_input("Nuova Password", type="password")
            c_pw = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA E ATTIVA ACCOUNT"):
                if n_pw == c_pw and len(n_pw) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = n_pw
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success("Password aggiornata! Accesso in corso..."); st.rerun()
                else: st.error("Le password non coincidono o sono troppo brevi (min. 4 caratteri).")
        st.stop() # FERMA TUTTO QUI SE NON CAMBIANO LA PW

    # 3. INTERFACCIA NORMALE (CARICATA SOLO SE PRIMOACCESSO == 0)
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl="1m")
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
    except: df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    st.sidebar.info(f"👤 {st.session_state.utente_loggato}")
    menu_options = ["Dashboard", "Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper(): menu_options.append("Admin")
    scelta = st.sidebar.radio("Navigazione", menu_options)
    if st.sidebar.button("Logout"): st.session_state.autenticato = False; st.rerun()

    if scelta == "Dashboard":
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{utente_row['Ferie']} gg")
        c2.metric("ROL residui", f"{utente_row['ROL']} ore")
        c3.metric("Contratto", utente_row['Contratto'])

    elif scelta == "Invia Richiesta":
        with st.form("richiesta"):
            t = st.selectbox("Tipo", ["Ferie", "ROL", "104", "Congedo"])
            p = st.date_input("Periodo", value=())
            n = st.text_area("Note")
            if st.form_submit_button("Invia"):
                if len(p) == 2:
                    giorni = pd.date_range(start=p[0], end=p[1])
                    nuove_rows = []
                    for gx in giorni:
                        nuove_rows.append({"Data_Richiesta": datetime.now().strftime("%d/%m/%Y"), "Nome": st.session_state.utente_loggato, "Tipo": t, "Periodo": str(gx.date()), "Note": n})
                    conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove_rows)], ignore_index=True))
                    invia_notifica_email(st.session_state.utente_loggato, t, f"{p[0]} - {p[1]}", n)
                    st.success("Richiesta registrata!"); st.balloons()

    elif scelta == "Admin":
        t1, t2, t3, t4, t5 = st.tabs(["MATRICE", "LIMITI", "AGGIUNGI", "ELIMINA", "DATABASE"])
        
        with t1:
            st.subheader("Pianificazione Lun-Dom")
            oggi = datetime.now().date()
            lun = oggi - timedelta(days=oggi.weekday())
            sett = [lun + timedelta(days=i) for i in range(7)]
            df_richieste['Data_G'] = pd.to_datetime(df_richieste['Periodo']).dt.date
            assenti = df_richieste[df_richieste['Data_G'].isin(sett)]['Nome'].unique()
            if len(assenti) > 0:
                mat = []
                for d in sorted(assenti):
                    row = {"Dipendente": d}
                    for g in sett:
                        col = g.strftime('%a %d/%m')
                        match = df_richieste[(df_richieste['Nome'] == d) & (df_richieste['Data_G'] == g)]
                        row[col] = match['Tipo'].values[0] if not match.empty else "-"
                    mat.append(row)
                st.dataframe(pd.DataFrame(mat).set_index("Dipendente"), use_container_width=True)
            else: st.info("Tutti presenti questa settimana.")

        with t2:
            st.subheader("Tetti massimi assenze")
            if not df_limiti.empty:
                with st.form("limiti_f"):
                    nuovi = {}
                    for _, r in df_limiti.iterrows():
                        nuovi[r['Mese']] = st.number_input(f"Limite {r['Mese']}", 1, 15, int(r['Limite']))
                    if st.form_submit_button("Aggiorna Limiti"):
                        conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi.items()), columns=['Mese', 'Limite']))
                        st.success("Limiti salvati!"); st.rerun()

        with t3:
            st.subheader("Inserisci nuova risorsa")
            with st.form("add_f"):
                nome_n = st.text_input("Nome Cognome").upper()
                cont_n = st.selectbox("Contratto", ["Fiduciario", "Armato", "Admin"])
                if st.form_submit_button("Registra Dipendente"):
                    if nome_n:
                        n_r = {"Nome": nome_n, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": cont_n, "PrimoAccesso": "1"}
                        conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([n_r])], ignore_index=True))
                        st.success(f"{nome_n} registrato!"); st.rerun()

        with t4:
            st.subheader("Rimuovi Dipendente")
            chi = st.selectbox("Chi vuoi eliminare?", ["---"] + df_dip['Nome'].tolist())
            if st.button("CONFERMA ELIMINAZIONE", type="primary"):
                if chi != "---":
                    conn.update(worksheet="Dipendenti", data=df_dip[df_dip['Nome'] != chi].drop(columns=['Nome_Display']))
                    st.success(f"{chi} rimosso."); st.rerun()

        with t5:
            st.dataframe(df_richieste)
