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
    mittente = "tua_email@gmail.com"  
    password = "la_tua_app_password"   
    destinatario = "ufficio_personale@esempio.it" 
    msg = MIMEMultipart()
    msg['From'] = mittente; msg['To'] = destinatario
    msg['Subject'] = f"RICHIESTA ASSENZA: {utente} - {tipo}"
    corpo = f"Dettagli:\nDipendente: {utente}\nTipo: {tipo}\nPeriodo: {periodo}\nNote: {note}"
    msg.attach(MIMEText(corpo, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
        server.login(mittente, password); server.send_message(msg); server.quit()
        return True
    except: return False

# --- CARICAMENTO DATI ---
try:
    # TTL=0 per evitare che Streamlit usi vecchi dati in memoria
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_dip.columns = df_dip.columns.str.strip()
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()
except Exception as e:
    st.error(f"Errore critico database: {e}"); st.stop()

if "autenticato" not in st.session_state: st.session_state.autenticato = False
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None

st.title("🏥 Sistema Gestione Assenze BTV")

# --- LOGIN ---
if not st.session_state.autenticato:
    with st.form("login_form"):
        user = st.selectbox("Seleziona il tuo Nome", df_dip['Nome_Display'].tolist())
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("ACCEDI"):
            val = df_dip[(df_dip['Nome_Display'] == user) & (df_dip['Password'].astype(str).str.strip() == str(pw).strip())]
            if not val.empty:
                st.session_state.autenticato = True
                st.session_state.utente_loggato = user
                st.rerun()
            else: st.error("Password errata!")

# --- AREA RISERVATA ---
else:
    # 1. Recupero riga utente
    dati_u = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]
    
    # 2. DEBUGGER (LO TOLGLIEREMO APPENA FUNZIONA)
    # st.write(f"DEBUG: Il valore di PrimoAccesso per te è: '{dati_u['PrimoAccesso']}'")

    # 3. TRASFORMAZIONE FORZATA: Convertiamo in stringa, togliamo il .0 se presente, e leviamo spazi
    stato_pw = str(dati_u['PrimoAccesso']).replace('.0', '').strip()

    # --- CONTROLLO CAMBIO PASSWORD ---
    if stato_pw == "1":
        st.header("🔑 Cambio Password Obbligatorio")
        st.error(f"ATTENZIONE: Devi cambiare la password prima di proseguire.")
        
        with st.form("cambio_pw_form"):
            n_pw = st.text_input("Nuova Password", type="password")
            c_pw = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA PASSWORD"):
                if n_pw == c_pw and len(n_pw) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = str(n_pw).strip()
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    
                    # Salvataggio
                    df_salva = df_dip.drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_salva)
                    st.success("✅ Password salvata! Ricaricamento..."); st.rerun()
                else:
                    st.error("Le password non coincidono o sono troppo brevi.")
        st.stop()

    # --- RESTO DEL CODICE (ACCESSIBILE SOLO SE PRIMOACCESSO == 0) ---
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl="1m")
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
    except:
        df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    st.sidebar.success(f"👤 {st.session_state.utente_loggato}")
    menu = ["📊 Dashboard", "📩 Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper(): menu.append("⚙️ Admin")
    scelta = st.sidebar.radio("Navigazione", menu)
    
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False; st.rerun()

    if scelta == "📊 Dashboard":
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{dati_u['Ferie']} gg")
        c2.metric("ROL residui", f"{dati_u['ROL']} ore")
        c3.metric("Contratto", dati_u['Contratto'])

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
                            st.error(f"Giorno {g.date()} completo (Max {lim_g})"); possibile = False; break
                    if possibile:
                        nuove = [{"Data_Richiesta": datetime.now().strftime("%d/%m/%Y"), "Nome": st.session_state.utente_loggato, "Tipo": tipo, "Periodo": str(gx.date()), "Note": note} for gx in giorni]
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True))
                        invia_notifica_email(st.session_state.utente_loggato, tipo, f"{per[0]} - {per[1]}", note)
                        st.success("Inviata!"); st.balloons()

    elif scelta == "⚙️ Admin":
        t1, t2, t3, t4, t5 = st.tabs(["📅 MATRICE LUN-DOM", "🔢 LIMITI MENSILI", "➕ AGGIUNGI", "🗑️ ELIMINA", "📊 DB"])
        with t1:
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
            else: st.info("Tutti presenti.")
        # ... (Resto delle tab Admin come prima) ...
