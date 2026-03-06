import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
import calendar
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="BTV - Gestione Assenze", layout="wide")

# Funzione per caricare i dati con cache per evitare Errore 429
@st.cache_data(ttl=600)  # Mantiene i dati in memoria per 10 minuti
def load_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    dip = conn.read(worksheet="Dipendenti", ttl=0)
    richieste = conn.read(worksheet="Richieste", ttl=0)
    limiti = conn.read(worksheet="Limiti_Mensili", ttl=0)
    try:
        blocchi = conn.read(worksheet="Blocchi", ttl=0)
    except:
        blocchi = pd.DataFrame(columns=['Data', 'Motivo'])
    return dip, richieste, limiti, blocchi

# --- 2. FUNZIONI DI SERVIZIO ---
def invia_mail(utente, tipo, periodo, note, azione="NUOVA RICHIESTA"):
    mittente = "tua_email@gmail.com"  # Inserire tua mail
    password = "la_tua_app_password"  # Inserire tua password app
    destinatario = "ufficio_personale@esempio.it" 
    msg = MIMEMultipart()
    msg['From'] = mittente; msg['To'] = destinatario
    msg['Subject'] = f"{azione}: {utente} - {tipo}"
    corpo = f"Dettagli:\nUtente: {utente}\nTipo: {tipo}\nPeriodo: {periodo}\nNote: {note}"
    msg.attach(MIMEText(corpo, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
        server.login(mittente, password); server.send_message(msg); server.quit()
        return True
    except: return False

# --- 3. INIZIALIZZAZIONE ---
df_dip, df_richieste, df_limiti, df_blocchi = load_all_data()
df_dip.columns = df_dip.columns.str.strip()
df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()

if "autenticato" not in st.session_state:
    st.session_state.autenticato = False

# --- 4. LOGICA ACCESSO ---
if not st.session_state.autenticato:
    st.title("🏥 Portale BTV")
    with st.form("login"):
        u = st.selectbox("Seleziona Utente", df_dip['Nome_Display'].tolist())
        p = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRA"):
            valid = df_dip[(df_dip['Nome_Display'] == u) & (df_dip['Password'].astype(str).str.strip() == str(p).strip())]
            if not valid.empty:
                st.session_state.autenticato = True
                st.session_state.utente_loggato = u
                st.rerun()
            else:
                st.error("Credenziali non valide")
else:
    # Recupero info utente loggato
    info = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]
    conn = st.connection("gsheets", type=GSheetsConnection)

    # Obbligo cambio password al primo accesso
    if str(info['PrimoAccesso']) == "1":
        st.warning("Sicurezza: cambia la tua password provvisoria.")
        with st.form("reset_pw"):
            n1 = st.text_input("Nuova Password", type="password")
            n2 = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("AGGIORNA"):
                if n1 == n2 and len(n1) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = n1
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.cache_data.clear()
                    st.success("Fatto! Accedi di nuovo.")
                    st.session_state.autenticato = False
                    st.rerun()
                else: st.error("Errore password.")
        st.stop()

    # Sidebar Navigazione
    st.sidebar.info(f"Utente: {st.session_state.utente_loggato}")
    pagine = ["📊 Dashboard", "📩 Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        pagine.append("⚙️ Admin")
    scelta = st.sidebar.radio("Vai a:", pagine)
    if st.sidebar.button("Esci"):
        st.session_state.autenticato = False
        st.rerun()

    # Date cardine
    oggi = datetime.now().date()
    prox_lunedi = oggi + timedelta(days=(7 - oggi.weekday()))

    # --- PAGINA DASHBOARD ---
    if scelta == "📊 Dashboard":
        st.header("I tuoi saldi")
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie Residue", f"{info['Ferie']} gg")
        c2.metric("ROL Residui", f"{info['ROL']} ore")
        c3.metric("Tipo Contratto", info['Contratto'])

        st.divider()
        st.subheader("Annullamento Richieste (dalla settimana prossima)")
        mie = df_richieste[df_richieste['Nome'] == st.session_state.utente_loggato].copy()
        if not mie.empty:
            mie['Data_DT'] = pd.to_datetime(mie['Periodo']).dt.date
            future = mie[mie['Data_DT'] >= prox_lunedi].sort_values('Data_DT')
            if not future.empty:
                for i, r in future.iterrows():
                    colA, colB = st.columns([3, 1])
                    colA.write(f"📅 **{r['Periodo']}** - {r['Tipo']}")
                    if colB.button("Annulla", key=f"del_{i}"):
                        nuovo_df = df_richieste.drop(i)
                        conn.update(worksheet="Richieste", data=nuovo_df)
                        invia_mail(st.session_state.utente_loggato, r['Tipo'], r['Periodo'], "CANCELLAZIONE", "RICHIESTA ANNULLATA")
                        st.cache_data.clear()
                        st.rerun()
            else: st.info("Nessuna richiesta futura cancellabile.")
        else: st.info("Nessuna prenotazione presente.")

    # --- PAGINA INVIO RICHIESTA ---
    elif scelta == "📩 Invia Richiesta":
        st.header("Prenotazione")
        st.info(f"Puoi prenotare solo dal Lunedì successivo: {prox_lunedi.strftime('%d/%m/%Y')}")

        # Calendario compatto
        anno, mese = oggi.year, oggi.month
        nome_mese = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"][mese-1]
        
        cal = calendar.monthcalendar(anno, mese)
        limite = 3
        if not df_limiti.empty:
            match = df_limiti[df_limiti['Mese'].str.lower() == nome_mese.lower()]
            if not match.empty: limite = int(match['Limite'].values[0])

        cols_head = st.columns(7)
        giorni = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        for idx, g in enumerate(giorni): cols_head[idx].write(f"**{g}**")

        for sett in cal:
            cols = st.columns(7)
            for idx, giorno in enumerate(sett):
                if giorno != 0:
                    data_s = f"{anno}-{mese:02d}-{giorno:02d}"
                    occ = df_richieste[df_richieste['Periodo'].astype(str) == data_s].shape[0]
                    bloccato = data_s in df_blocchi['Data'].astype(str).values
                    
                    if bloccato: ico = "🔒"
                    elif occ >= limite: ico = "🔴"
                    elif occ == limite - 1: ico = "🟡"
                    else: ico = "🟢"
                    cols[idx].markdown(f"{giorno}<br>{ico}", unsafe_allow_html=True)

        st.divider()
        with st.form("form_richiesta"):
            tipo = st.selectbox("Causale", ["Ferie", "ROL", "104", "Congedo"])
            periodo = st.date_input("Seleziona periodo", value=(), min_value=prox_lunedi)
            note = st.text_area("Note aggiuntive")
            if st.form_submit_button("INVIA RICHIESTA"):
                if len(periodo) == 2:
                    range_g = pd.date_range(start=periodo[0], end=periodo[1])
                    esente = str(info.get('SenzaLimiti', '0')) == "1"
                    ok = True
                    for g in range_g:
                        g_str = str(g.date())
                        if g_str in df_blocchi['Data'].astype(str).values:
                            st.error(f"Data {g_str} bloccata dall'amministrazione."); ok = False; break
                        occ_g = df_richieste[df_richieste['Periodo'].astype(str) == g_str].shape[0]
                        if not esente and tipo in ["Ferie", "ROL"] and occ_g >= limite:
                            st.error(f"Limite raggiunto per il giorno {g_str}"); ok = False; break
                    
                    if ok:
                        nuove = [{"Data_Richiesta": oggi.strftime("%d/%m/%Y"), "Nome": st.session_state.utente_loggato, "Tipo": tipo, "Periodo": str(gx.date()), "Note": note} for gx in range_g]
                        df_richieste = pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True)
                        conn.update(worksheet="Richieste", data=df_richieste)
                        invia_mail(st.session_state.utente_loggato, tipo, str(periodo), note)
                        st.cache_data.clear()
                        st.success("Richiesta registrata!"); st.balloons(); st.rerun()
                else: st.warning("Seleziona data inizio e fine.")

    # --- PAGINA AMMINISTRAZIONE ---
    elif scelta == "⚙️ Admin":
        t1, t2, t3, t4 = st.tabs(["MATRICE SETT. PROX", "GESTIONE UTENTI", "BLOCCHI E LIMITI", "LOG"])

        with t1:
            st.write(f"Pianificazione dal {prox_lunedi.strftime('%d/%m')}")
            sett_prox = [prox_lunedi + timedelta(days=i) for i in range(7)]
            df_richieste['Data_G'] = pd.to_datetime(df_richieste['Periodo']).dt.date
            nomi_assenti = df_richieste[df_richieste['Data_G'].isin(sett_prox)]['Nome'].unique()
            if len(nomi_assenti) > 0:
                matrice = []
                for n in sorted(nomi_assenti):
                    riga = {"Dipendente": n}
                    for g in sett_prox:
                        causale = df_richieste[(df_richieste['Nome'] == n) & (df_richieste['Data_G'] == g)]['Tipo'].values
                        riga[g.strftime('%a %d/%m')] = causale[0] if len(causale) > 0 else "-"
                    matrice.append(riga)
                st.dataframe(pd.DataFrame(matrice).set_index("Dipendente"), use_container_width=True)
            else: st.info("Nessun assente pianificato.")

        with t2:
            st.subheader("Reset e Cancellazione")
            colX, colY = st.columns(2)
            with colX:
                u_res = st.selectbox("Reset Password a 12345", ["---"] + df_dip['Nome'].tolist(), key="r1")
                if st.button("ESEGUI RESET"):
                    if u_res != "---":
                        idx = df_dip[df_dip['Nome'] == u_res].index[0]
                        df_dip.at[idx, 'Password'] = "12345"
                        df_dip.at[idx, 'PrimoAccesso'] = "1"
                        conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                        st.cache_data.clear(); st.success("Reset OK"); st.rerun()
            with colY:
                u_del = st.selectbox("Elimina Utente", ["---"] + df_dip['Nome'].tolist(), key="d1")
                if st.button("ELIMINA DEFINITIVAMENTE", type="primary"):
                    if u_del != "---":
                        df_new = df_dip[df_dip['Nome'] != u_del].drop(columns=['Nome_Display'])
                        conn.update(worksheet="Dipendenti", data=df_new)
                        st.cache_data.clear(); st.success("Utente eliminato"); st.rerun()
            
            st.divider()
            with st.expander("Aggiungi Nuovo Dipendente"):
                with st.form("new_u"):
                    n_n = st.text_input("Nome Cognome").upper()
                    n_c = st.selectbox("Contratto", ["Fiduciario", "Armato", "Admin"])
                    n_e = st.selectbox("Esenzione Limiti?", ["NO", "SI"])
                    if st.form_submit_button("SALVA"):
                        nuovo = {"Nome": n_n, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": n_c, "PrimoAccesso": "1", "SenzaLimiti": ("1" if n_e == "SI" else "0")}
                        df_dip = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=df_dip)
                        st.cache_data.clear(); st.rerun()

        with t3:
            st.subheader("Blocchi Date")
            with st.form("f_blocco"):
                d_b = st.date_input("Data da bloccare")
                m_b = st.text_input("Motivo")
                if st.form_submit_button("BLOCCA"):
                    nuovo_b = pd.DataFrame([{"Data": str(d_b), "Motivo": m_b}])
                    df_blocchi = pd.concat([df_blocchi, nuovo_b], ignore_index=True)
                    conn.update(worksheet="Blocchi", data=df_blocchi)
                    st.cache_data.clear(); st.rerun()
            if st.button("Svuota tutti i blocchi"):
                conn.update(worksheet="Blocchi", data=pd.DataFrame(columns=['Data', 'Motivo']))
                st.cache_data.clear(); st.rerun()

        with t4: st.dataframe(df_richieste)
