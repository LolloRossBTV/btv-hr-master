import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAZIONE INIZIALE ---
st.set_page_config(page_title="Gestione Presenze", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNZIONE INVIO E-MAIL ---
def invia_notifica_email(utente, tipo, periodo, note):
    # --- CONFIGURA QUI I TUOI DATI ---
    mittente = "rossini.lzo@gmail.com"  # La tua mail
    password = "spav pctg oolm cnps"   # La password per app (non quella normale se usi Gmail)
    destinatario = "lorenzo.rossini@battistolli.it" # Mail di chi riceve
    
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = destinatario
    msg['Subject'] = f"NUOVA RICHIESTA ASSENZA: {utente}"

    corpo = f"""
    È stata inserita una nuova richiesta sul portale:
    
    - Dipendente: {utente}
    - Tipo: {tipo}
    - Periodo: {periodo}
    - Note: {note}
    
    Messaggio generato automaticamente dal Sistema Presenze.
    """
    msg.attach(MIMEText(corpo, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mittente, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Errore tecnico invio mail: {e}")
        return False

# --- CARICAMENTO DIPENDENTI ---
try:
    df_dip = conn.read(worksheet="Dipendenti", ttl="0")
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper()
except Exception as e:
    st.error("Errore di connessione a Google Sheets. Verifica il database.")
    st.stop()

# --- STATO SESSIONE ---
if "autenticato" not in st.session_state:
    st.session_state.autenticato = False
if "utente_loggato" not in st.session_state:
    st.session_state.utente_loggato = None

st.title("🏥 Sistema Gestione Assenze")

# --- LOGIN ---
if not st.session_state.autenticato:
    with st.form("login_form"):
        st.subheader("Accedi al Portale")
        user = st.selectbox("Seleziona il tuo nome", df_dip['Nome_Display'].tolist())
        password = st.text_input("Inserisci Password", type="password")
        
        if st.form_submit_button("ENTRA"):
            validazione = df_dip[(df_dip['Nome_Display'] == user) & (df_dip['Password'].astype(str) == password)]
            if not validazione.empty:
                st.session_state.autenticato = True
                st.session_state.utente_loggato = user
                st.rerun()
            else:
                st.error("❌ Password errata!")

# --- AREA PRIVATA ---
else:
    nome_u = st.session_state.utente_loggato
    dati_u = df_dip[df_dip['Nome_Display'] == nome_u].iloc[0]
    
    # 1. Controllo Cambio Password
    if str(dati_u['PrimoAccesso']) == "1":
        st.warning(f"👋 Ciao {nome_u}, devi cambiare la password al primo accesso.")
        with st.form("cambio_pass"):
            n_p = st.text_input("Nuova Password", type="password")
            c_p = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA E ACCEDI"):
                if n_p == c_p and len(n_p) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == nome_u].index[0]
                    df_dip.at[idx, 'Password'] = n_p
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success("✅ Password aggiornata!"); st.rerun()
                else: st.error("Le password non coincidono o sono troppo corte.")
        st.stop()

    # 2. Caricamento Dati Tabelle
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl="1m")
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
    except:
        df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    # 3. Sidebar Menu
    st.sidebar.success(f"👤 {nome_u}")
    menu = ["📊 Dashboard Saldi", "📩 Invia Richiesta"]
    if "ROSSINI" in nome_u.upper(): menu.append("⚙️ Pannello Admin")
    scelta = st.sidebar.radio("Vai a:", menu)
    
    if st.sidebar.button("Logout", type="primary"):
        st.session_state.autenticato = False; st.rerun()

    # 4. Sezioni
    if scelta == "📊 Dashboard Saldi":
        st.header(f"Benvenuto, {nome_u}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{dati_u['Ferie']} gg")
        c2.metric("ROL residui", f"{dati_u['ROL']} ore")
        c3.metric("Contratto", dati_u['Contratto'])
elif scelta == "📩 Invia Richiesta":
        st.header("Inserimento Assenza")
        with st.form("form_invio"):
            # 1. Lista causali aggiornata (senza malattia)
            tipo = st.selectbox("Motivazione", ["Ferie", "ROL", "104", "Congedo Parentale", "Congedo Matrimoniale"])
            periodo = st.date_input("Periodo (Inizio e Fine)", value=())
            note = st.text_area("Eventuali note")
            
            if st.form_submit_button("Verifica e Invia"):
                if len(periodo) == 2:
                    giorni = pd.date_range(start=periodo[0], end=periodo[1])
                    mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
                    
                    possibile = True
                    for g in giorni:
                        m_n = mesi_it[g.month - 1]
                        lim = 3
                        if not df_limiti.empty:
                            lim_r = df_limiti[df_limiti['Mese'] == m_n]
                            if not lim_r.empty: lim = int(lim_r['Limite'].values[0])
                        
                        occ = df_richieste[df_richieste['Periodo'].astype(str) == str(g.date())].shape[0]
                        if tipo in ["Ferie", "ROL"] and occ >= lim:
                            st.error(f"❌ Il {g.strftime('%d/%m')} è pieno."); possibile = False; break
                    
                    if possibile:
                        # SALVA SU GOOGLE SHEETS
                        nuove = [{"Data_Richiesta": pd.Timestamp.now().strftime("%d/%m/%Y"), "Nome": nome_u, "Tipo": tipo, "Periodo": str(gx.date()), "Note": note} for gx in giorni]
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True))
                        
                        # INVIO E-MAIL (Configura mittente/password nella funzione in alto se l'hai messa)
                        periodo_str = f"dal {periodo[0]} al {periodo[1]}"
                        invia_notifica_email(nome_u, tipo, periodo_str, note)
                        
                        st.success("✅ Richiesta salvata e notifica inviata!"); st.balloons()
                else: st.warning("Seleziona Inizio e Fine.")

    elif scelta == "⚙️ Pannello Admin":
        st.header("Amministrazione")
        t_ods, t_lim, t_add, t_db = st.tabs(["📅 MATRICE LUN-DOM", "🔢 LIMITI", "➕ NUOVO", "📊 DATABASE"])
        
        with t_ods:
            st.subheader("Pianificazione Settimanale (Lunedì - Domenica)")
            # CALCOLO SETTIMANA CORRENTE (LUN-DOM)
            oggi = pd.Timestamp.now().date()
            lunedi = oggi - pd.Timedelta(days=oggi.weekday())
            settimana = [lunedi + pd.Timedelta(days=i) for i in range(7)]
            
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
            else: st.info("Nessuna assenza programmata per questa settimana.")

        with t_lim:
            if not df_limiti.empty:
                nuovi_l = {}
                c1, c2, c3 = st.columns(3)
                for i, r in df_limiti.iterrows():
                    with [c1, c2, c3][i % 3]: nuovi_l[r['Mese']] = st.number_input(r['Mese'].capitalize(), 1, 15, int(r['Limite']), key=f"l_{r['Mese']}")
                if st.button("Aggiorna Limiti"):
                    conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi_l.items()), columns=['Mese', 'Limite']))
                    st.success("Limiti salvati!"); st.rerun()

        with t_add:
            with st.form("add_new"):
                nn = st.text_input("Nome e Cognome").upper()
                cc = st.selectbox("Contratto", ["Fiduciario", "Armato", "Amministrativo"])
                if st.form_submit_button("REGISTRA NUOVO"):
                    nuovo = {"Nome": nn, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": cc, "PrimoAccesso": "1"}
                    conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True))
                    st.success(f"{nn} aggiunto correttamente!"); st.rerun()

        with t_db:
            st.dataframe(df_richieste, use_container_width=True)
   
