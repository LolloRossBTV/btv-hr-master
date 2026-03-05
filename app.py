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
    # INSERISCI I TUOI DATI QUI SOTTO
    mittente = "tua_email@gmail.com"  
    password = "la_tua_app_password"   
    destinatario = "ufficio_personale@esempio.it" 
    msg = MIMEMultipart()
    msg['From'] = mittente; msg['To'] = destinatario
    msg['Subject'] = f"RICHIESTA: {utente} - {tipo}"
    corpo = f"Dipendente: {utente}\nTipo: {tipo}\nPeriodo: {periodo}\nNote: {note}"
    msg.attach(MIMEText(corpo, 'plain'))
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
    st.error("Errore di connessione a Google Sheets."); st.stop()

if "autenticato" not in st.session_state: st.session_state.autenticato = False
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None

st.title("🏥 Sistema Gestione Assenze BTV")

# --- LOGIN ---
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

# --- AREA RISERVATA ---
else:
    dati_u = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]

    # --- CONTROLLO CAMBIO PW ---
    if dati_u['PrimoAccesso'] == "1":
        st.header("🔑 Cambio Password Obbligatorio")
        with st.form("pw_obbligatorio"):
            n_pw = st.text_input("Nuova Password", type="password")
            c_pw = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA"):
                if n_pw == c_pw and len(n_pw) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = n_pw; df_dip.at[idx, 'PrimoAccesso'] = "0"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success("Fatto!"); st.rerun()
                else: st.error("Errore password.")
        st.stop()

    # --- NAVIGAZIONE ---
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl="1m")
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
    except: df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    st.sidebar.info(f"👤 {st.session_state.utente_loggato}")
    scelta = st.sidebar.radio("Menu", ["Dashboard", "Invia Richiesta", "Admin"] if "ROSSINI" in st.session_state.utente_loggato.upper() else ["Dashboard", "Invia Richiesta"])
    if st.sidebar.button("Logout"): st.session_state.autenticato = False; st.rerun()

    if scelta == "Dashboard":
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{dati_u['Ferie']} gg")
        c2.metric("ROL residui", f"{dati_u['ROL']} ore")
        c3.metric("Contratto", dati_u['Contratto'])

    elif scelta == "Invia Richiesta":
        with st.form("richiesta"):
            t = st.selectbox("Tipo", ["Ferie", "ROL", "104", "Congedo"])
            p = st.date_input("Periodo", value=())
            n = st.text_area("Note")
            if st.form_submit_button("Invia"):
                if len(p) == 2:
                    giorni = pd.date_range(start=p[0], end=p[1])
                    for gx in giorni:
                        nuova = {"Data_Richiesta": datetime.now().strftime("%d/%m/%Y"), "Nome": st.session_state.utente_loggato, "Tipo": t, "Periodo": str(gx.date()), "Note": n}
                        df_richieste = pd.concat([df_richieste, pd.DataFrame([nuova])], ignore_index=True)
                    conn.update(worksheet="Richieste", data=df_richieste)
                    invia_notifica_email(st.session_state.utente_loggato, t, str(p), n)
                    st.success("Inviato!"); st.balloons()

    elif scelta == "Admin":
        t1, t2, t3, t4, t5 = st.tabs(["MATRICE", "LIMITI", "AGGIUNGI", "ELIMINA", "DB"])
        
        with t1:
            st.subheader("Pianificazione Settimanale")
            oggi = datetime.now().date()
            lun = oggi - timedelta(days=oggi.weekday())
            sett = [lun + timedelta(days=i) for i in range(7)]
            df_richieste['Data_G'] = pd.to_datetime(df_richieste['Periodo']).dt.date
            assenti = df_richieste[df_richieste['Data_G'].isin(sett)]['Nome'].unique()
            if len(assenti) > 0:
                mat = []
                for d in sorted(assenti):
                    r = {"Dipendente": d}
                    for g in sett:
                        col = g.strftime('%a %d/%m')
                        m = df_richieste[(df_richieste['Nome'] == d) & (df_richieste['Data_G'] == g)]
                        r[col] = m['Tipo'].values[0] if not m.empty else "-"
                    mat.append(r)
                st.dataframe(pd.DataFrame(mat).set_index("Dipendente"), use_container_width=True)
            else: st.info("Tutti presenti.")

        with t2:
            st.subheader("Limiti Assenze")
            if not df_limiti.empty:
                with st.form("limiti_f"):
                    nuovi = {}
                    for i, r in df_limiti.iterrows():
                        nuovi[r['Mese']] = st.number_input(f"Limite {r['Mese']}", 1, 10, int(r['Limite']))
                    if st.form_submit_button("Salva"):
                        conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi.items()), columns=['Mese', 'Limite']))
                        st.success("OK!"); st.rerun()

        with t3:
            st.subheader("Nuovo Dipendente")
            with st.form("add_f"):
                nome_n = st.text_input("Nome").upper()
                cont_n = st.selectbox("Contratto", ["Fiduciario", "Armato"])
                if st.form_submit_button("Aggiungi"):
                    n_r = {"Nome": nome_n, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": cont_n, "PrimoAccesso": "1"}
                    conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([n_r])], ignore_index=True))
                    st.success("Aggiunto!"); st.rerun()

        with t4:
            st.subheader("Elimina Dipendente")
            chi = st.selectbox("Seleziona", ["---"] + df_dip['Nome'].tolist())
            if st.button("ELIMINA", type="primary"):
                if chi != "---":
                    conn.update(worksheet="Dipendenti", data=df_dip[df_dip['Nome'] != chi].drop(columns=['Nome_Display']))
                    st.success("Eliminato!"); st.rerun()

        with t5:
            st.dataframe(df_richieste)
