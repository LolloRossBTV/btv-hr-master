import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE E CONNESSIONE ---
st.set_page_config(page_title="Sistema Gestione Assenze BTV", layout="wide")

# Pulizia cache per garantire dati sempre aggiornati
st.cache_data.clear()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. FUNZIONE INVIO MAIL ---
def invia_notifica_email(utente, tipo, periodo, note):
    mittente = "tua_email@gmail.com"  # <--- Inserisci la tua mail
    password = "la_tua_app_password"   # <--- Inserisci la password app di Google
    destinatario = "ufficio_personale@esempio.it" 
    
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = destinatario
    msg['Subject'] = f"RICHIESTA ASSENZA: {utente} - {tipo}"
    corpo = f"Nuova richiesta:\nDipendente: {utente}\nTipo: {tipo}\nPeriodo: {periodo}\nNote: {note}"
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

# --- 3. CARICAMENTO DATI ---
try:
    # Carico i dipendenti
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_dip.columns = df_dip.columns.str.strip()
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()
    
    # Pulizia PrimoAccesso e SenzaLimiti
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.replace('.0', '', regex=False).str.strip()
    if 'SenzaLimiti' not in df_dip.columns:
        df_dip['SenzaLimiti'] = "0"
    else:
        df_dip['SenzaLimiti'] = df_dip['SenzaLimiti'].astype(str).str.replace('.0', '', regex=False).str.strip()
        
except Exception as e:
    st.error(f"Errore caricamento database: {e}")
    st.stop()

# Gestione Sessione
if "autenticato" not in st.session_state:
    st.session_state.autenticato = False
if "utente_loggato" not in st.session_state:
    st.session_state.utente_loggato = None

st.title("🏥 Sistema Gestione Assenze BTV")

# --- 4. LOGICA ACCESSO (LOGIN) ---
if not st.session_state.autenticato:
    with st.form("login_form"):
        u = st.selectbox("Seleziona il tuo Nome", df_dip['Nome_Display'].tolist())
        p = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRA"):
            validazione = df_dip[(df_dip['Nome_Display'] == u) & (df_dip['Password'].astype(str).str.strip() == str(p).strip())]
            if not validazione.empty:
                st.session_state.autenticato = True
                st.session_state.utente_loggato = u
                st.rerun()
            else:
                st.error("Password errata!")

# --- 5. AREA RISERVATA ---
else:
    # Dati dell'utente corrente
    utente_info = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]
    
    # --- CONTROLLO CAMBIO PASSWORD OBBLIGATORIO ---
    if utente_info['PrimoAccesso'] == "1":
        st.warning(f"⚠️ SICUREZZA: {st.session_state.utente_loggato}, devi impostare una nuova password personale.")
        with st.form("cambio_pw_form"):
            n1 = st.text_input("Nuova Password", type="password")
            n2 = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA E ACCEDI"):
                if n1 == n2 and len(n1) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = n1
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success("Password salvata!")
                    st.rerun()
                else:
                    st.error("Le password non coincidono o sono troppo corte (min. 4 car).")
        st.stop() # Impedisce di vedere il menu se non cambia la password

    # --- CARICAMENTO RICHIESTE E LIMITI ---
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl=0)
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl=0)
    except:
        df_richieste = pd.DataFrame(columns=['Data_Richiesta', 'Nome', 'Tipo', 'Periodo', 'Note'])
        df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    # --- NAVIGAZIONE SIDEBAR ---
    st.sidebar.info(f"👤 {st.session_state.utente_loggato}")
    pagine = ["📊 Dashboard", "📩 Invia Richiesta"]
    
    # Accesso Admin solo per Rossini
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        pagine.append("⚙️ Admin")
    
    scelta = st.sidebar.radio("Navigazione:", pagine)
    
    if st.sidebar.button("Log-out"):
        st.session_state.autenticato = False
        st.rerun()

    # --- PAGINA: DASHBOARD ---
    if scelta == "📊 Dashboard":
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{utente_info['Ferie']} gg")
        c2.metric("ROL residui", f"{utente_info['ROL']} ore")
        c3.metric("Contratto", utente_info['Contratto'])

    # --- PAGINA: INVIA RICHIESTA ---
    elif scelta == "📩 Invia Richiesta":
        with st.form("richiesta_form"):
            t = st.selectbox("Tipo", ["Ferie", "ROL", "104", "Congedo"])
            p = st.date_input("Periodo (Seleziona inizio e fine)", value=())
            n = st.text_area("Note")
            
            if st.form_submit_button("Invia Richiesta"):
                if len(p) == 2:
                    giorni = pd.date_range(start=p[0], end=p[1])
                    
                    # Logica SenzaLimiti
                    esente = str(utente_info.get('SenzaLimiti', '0')).strip() == "1"
                    possibile = True
                    
                    if not esente:
                        for g in giorni:
                            mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
                            m_nome = mesi_it[g.month - 1]
                            limite_giorno = 3 # default
                            
                            if not df_limiti.empty:
                                search_lim = df_limiti[df_limiti['Mese'].str.lower() == m_nome.lower()]
                                if not search_lim.empty:
                                    limite_giorno = int(search_lim['Limite'].values[0])
                            
                            occ = df_richieste[df_richieste['Periodo'].astype(str) == str(g.date())].shape[0]
                            if t in ["Ferie", "ROL"] and occ >= limite_giorno:
                                st.error(f"❌ Giorno {g.date()} completo (Max {limite_giorno} persone).")
                                possibile = False
                                break
                    
                    if possibile:
                        nuove = []
                        for g in giorni:
                            nuove.append({
                                "Data_Richiesta": datetime.now().strftime("%d/%m/%Y"),
                                "Nome": st.session_state.utente_loggato,
                                "Tipo": t,
                                "Periodo": str(g.date()),
                                "Note": n
                            })
                        updated_df = pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True)
                        conn.update(worksheet="Richieste", data=updated_df)
                        invia_notifica_email(st.session_state.utente_loggato, t, str(p), n)
                        st.success("Richiesta registrata!"); st.balloons()
                else:
                    st.warning("Seleziona entrambe le date del periodo.")

    # --- PAGINA: ADMIN ---
    elif scelta == "⚙️ Admin":
        t1, t2, t3, t4, t5 = st.tabs(["MATRICE", "LIMITI", "AGGIUNGI", "ELIMINA", "DB"])
        
        with t1: # Matrice
            st.subheader("Pianificazione Settimanale")
            oggi = datetime.now().date()
            lun = oggi - timedelta(days=oggi.weekday())
            sett = [lun + timedelta(days=i) for i in range(7)]
            df_richieste['Data_G'] = pd.to_datetime(df_richieste['Periodo']).dt.date
            assenti = df_richieste[df_richieste['Data_G'].isin(sett)]['Nome'].unique()
            if len(assenti) > 0:
                mat_data = []
                for d in sorted(assenti):
                    r_mat = {"Dipendente": d}
                    for g in sett:
                        c_n = g.strftime('%a %d/%m')
                        m = df_richieste[(df_richieste['Nome'] == d) & (df_richieste['Data_G'] == g)]
                        r_mat[c_n] = m['Tipo'].values[0] if not m.empty else "-"
                    mat_data.append(r_mat)
                st.dataframe(pd.DataFrame(mat_data).set_index("Dipendente"), use_container_width=True)
            else: st.info("Nessuna assenza questa settimana.")

        with t2: # Limiti
            with st.form("limiti_form"):
                nuovi_lim = {}
                for idx, row in df_limiti.iterrows():
                    nuovi_lim[row['Mese']] = st.number_input(f"Limite {row['Mese']}", 1, 15, int(row['Limite']))
                if st.form_submit_button("Salva Limiti"):
                    conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi_lim.items()), columns=['Mese', 'Limite']))
                    st.success("Limiti salvati!"); st.rerun()

        with t3: # Aggiungi
            with st.form("add_form"):
                nn = st.text_input("Nome e Cognome").upper()
                cc = st.selectbox("Contratto", ["Fiduciario", "Armato", "Admin"])
                ee = st.selectbox("Esenzione Limiti?", ["NO", "SI"])
                if st.form_submit_button("Aggiungi Dipendente"):
                    if nn:
                        flag_e = "1" if ee == "SI" else "0"
                        nuovo_dip = {"Nome": nn, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": cc, "PrimoAccesso": "1", "SenzaLimiti": flag_e}
                        updated_dip = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo_dip])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=updated_dip)
                        st.success(f"{nn} aggiunto correttamente!"); st.rerun()

        with t4: # Elimina
            chi = st.selectbox("Seleziona chi rimuovere", ["---"] + df_dip['Nome'].tolist())
            if st.button("ELIMINA ORA", type="primary"):
                if chi != "---":
                    df_del = df_dip[df_dip['Nome'] != chi].drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_del)
                    st.success("Rimosso."); st.rerun()

        with t5: # Visualizza DB
            st.dataframe(df_richieste)
