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
    df_dip = conn.read(worksheet="Dipendenti", ttl="0")
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip()
except Exception as e:
    st.error("Errore di connessione a Google Sheets. Verifica il database.")
    st.stop()

if "autenticato" not in st.session_state: st.session_state.autenticato = False
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None

st.title("Sistema Gestione Assenze BTV")

# --- LOGICA LOGIN ---
if not st.session_state.autenticato:
    with st.form("login_form"):
        user = st.selectbox("Seleziona il tuo Nome", df_dip['Nome_Display'].tolist())
        pw = st.text_input("Inserisci Password", type="password")
        if st.form_submit_button("ACCEDI"):
            val = df_dip[(df_dip['Nome_Display'] == user) & (df_dip['Password'].astype(str).str.strip() == str(pw).strip())]
            if not val.empty:
                st.session_state.autenticato = True
                st.session_state.utente_loggato = user
                st.rerun()
            else: 
                st.error("Password errata!")

# --- AREA RISERVATA ---
else:
    nome_u = st.session_state.utente_loggato
    # Ricarica i dati per essere sicuri dello stato del PrimoAccesso
    dati_u = df_dip[df_dip['Nome_Display'] == nome_u].iloc[0]

    # --- SCHERMATA CAMBIO PASSWORD OBBLIGATORIO ---
    if dati_u['PrimoAccesso'] == "1":
        st.header("🔑 Cambio Password Obbligatorio")
        st.info("Questa è la tua prima sessione o la password è stata resettata. Scegli una nuova password per continuare.")
        
        with st.form("cambio_pw_obbligatorio"):
            nuova_pw = st.text_input("Nuova Password", type="password", help="Minimo 4 caratteri")
            conferma_pw = st.text_input("Conferma Nuova Password", type="password")
            
            if st.form_submit_button("SALVA NUOVA PASSWORD"):
                if nuova_pw == conferma_pw and len(nuova_pw) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == nome_u].index[0]
                    df_dip.at[idx, 'Password'] = str(nuova_pw).strip()
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    
                    df_salva = df_dip.drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_salva)
                    
                    st.success("Password aggiornata! Ora puoi usare il portale.")
                    st.balloons()
                    st.rerun()
                elif len(nuova_pw) < 4:
                    st.error("La password deve contenere almeno 4 caratteri.")
                else:
                    st.error("Le password non coincidono.")
        st.stop()

    # --- INTERFACCIA NORMALE (Dopo il cambio PW) ---
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl="1m")
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
    except:
        df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    st.sidebar.success(f"Utente: {nome_u}")
    menu = ["Dashboard", "Invia Richiesta"]
    if "ROSSINI" in nome_u.upper(): menu.append("Admin")
    
    scelta = st.sidebar.radio("Navigazione", menu)
    
    if st.sidebar.button("Esci (Logout)", key="logout_sidebar_unique"):
        st.session_state.autenticato = False
        st.session_state.utente_loggato = None
        st.rerun()

    # --- SEZIONI ---
    if scelta == "Dashboard":
        st.subheader("I tuoi contatori")
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{dati_u['Ferie']} gg")
        c2.metric("ROL residui", f"{dati_u['ROL']} ore")
        c3.metric("Contratto", dati_u['Contratto'])

    elif scelta == "Invia Richiesta":
        with st.form("form_richiesta"):
            tipo = st.selectbox("Tipo Assenza", ["Ferie", "ROL", "104", "Congedo Parentale", "Congedo Matrimoniale"])
            per = st.date_input("Seleziona Periodo", value=())
            note = st.text_area("Note")
            if st.form_submit_button("Invia Richiesta"):
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
                            st.error(f"Giorno {g.date()} completo (Max {lim_g})")
                            possibile = False; break
                    if possibile:
                        nuove = [{"Data_Richiesta": datetime.now().strftime("%d/%m/%Y"), "Nome": nome_u, "Tipo": tipo, "Periodo": str(gx.date()), "Note": note} for gx in giorni]
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True))
                        invia_notifica_email(nome_u, tipo, f"{per[0]} - {per[1]}", note)
                        st.success("Richiesta inviata con successo!"); st.balloons()

    elif scelta == "Admin":
        t1, t2, t3, t4, t5 = st.tabs(["Calendario Settimanale", "Limiti Mensili", "Aggiungi", "Elimina", "Database"])
        # Logica Admin (omessa qui per brevità ma integrata nel tuo sistema)
        # ... [Codice Admin come visto in precedenza] ...
