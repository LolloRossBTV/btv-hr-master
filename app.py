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
st.cache_data.clear()
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. FUNZIONI CORE ---
def invia_notifica_email(utente, tipo, periodo, note, azione="NUOVA RICHIESTA"):
    mittente = "tua_email@gmail.com" 
    password = "la_tua_app_password"
    destinatario = "ufficio_personale@esempio.it" 
    msg = MIMEMultipart()
    msg['From'] = mittente; msg['To'] = destinatario
    msg['Subject'] = f"{azione}: {utente} - {tipo}"
    corpo = f"Dettagli:\nDipendente: {utente}\nTipo: {tipo}\nPeriodo: {periodo}\nNote: {note}"
    msg.attach(MIMEText(corpo, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
        server.login(mittente, password); server.send_message(msg); server.quit()
        return True
    except: return False

# --- 3. CARICAMENTO DATI ---
try:
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_dip.columns = df_dip.columns.str.strip()
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()
    
    df_richieste = conn.read(worksheet="Richieste", ttl=0)
    df_limiti = conn.read(worksheet="Limiti_Mensili", ttl=0)
    
    # Caricamento Blocchi (se non esiste lo crea vuoto)
    try: df_blocchi = conn.read(worksheet="Blocchi", ttl=0)
    except: df_blocchi = pd.DataFrame(columns=['Data', 'Motivo'])
    
except Exception as e:
    st.error(f"Errore database: {e}"); st.stop()

if "autenticato" not in st.session_state: st.session_state.autenticato = False

# --- 4. LOGIN ---
if not st.session_state.autenticato:
    st.title("🏥 Accesso BTV")
    with st.form("login_form"):
        u = st.selectbox("Utente", df_dip['Nome_Display'].tolist())
        p = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRA"):
            valid = df_dip[(df_dip['Nome_Display'] == u) & (df_dip['Password'].astype(str).str.strip() == str(p).strip())]
            if not valid.empty:
                st.session_state.autenticato = True; st.session_state.utente_loggato = u; st.rerun()
            else: st.error("Password errata!")
else:
    utente_info = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]
    
    # Cambio PW Obbligatorio
    if str(utente_info['PrimoAccesso']) == "1":
        with st.form("pw"):
            st.warning("Reimposta la tua password personale")
            n1 = st.text_input("Nuova Password", type="password")
            n2 = st.text_input("Conferma", type="password")
            if st.form_submit_button("SALVA"):
                if n1 == n2 and len(n1) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = n1; df_dip.at[idx, 'PrimoAccesso'] = "0"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success("Password salvata!"); st.rerun()
        st.stop()

    # Sidebar
    st.sidebar.info(f"👤 {st.session_state.utente_loggato}")
    pagine = ["📊 Dashboard", "📩 Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper(): pagine.append("⚙️ Admin")
    scelta = st.sidebar.radio("Menu", pagine)
    if st.sidebar.button("Logout"): st.session_state.autenticato = False; st.rerun()

    oggi = datetime.now().date()
    prossimo_lunedi = oggi + timedelta(days=(7 - oggi.weekday()))

    # --- DASHBOARD (Con funzione ANNULLA) ---
    if scelta == "📊 Dashboard":
        st.subheader("I tuoi contatori")
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{utente_info['Ferie']} gg")
        c2.metric("ROL residue", f"{utente_info['ROL']} ore")
        c3.metric("Contratto", utente_info['Contratto'])

        st.divider()
        st.subheader("Le tue prenotazioni future")
        mie_richieste = df_richieste[df_richieste['Nome'] == st.session_state.utente_loggato].copy()
        mie_richieste['Data_DT'] = pd.to_datetime(mie_richieste['Periodo']).dt.date
        future = mie_richieste[mie_richieste['Data_DT'] >= prossimo_lunedi].sort_values('Data_DT')
        
        if not future.empty:
            for i, row in future.iterrows():
                col1, col2 = st.columns([4, 1])
                col1.write(f"📅 **{row['Periodo']}** - {row['Tipo']} ({row['Note']})")
                if col2.button("Annulla", key=f"del_{i}"):
                    df_new_richieste = df_richieste.drop(i)
                    conn.update(worksheet="Richieste", data=df_new_richieste)
                    invia_notifica_email(st.session_state.utente_loggato, row['Tipo'], row['Periodo'], "CANCELLAZIONE UTENTE", "RICHIESTA ANNULLATA")
                    st.success("Richiesta annullata"); st.rerun()
        else: st.info("Non hai prenotazioni dalla prossima settimana in poi.")

    # --- INVIA RICHIESTA ---
    elif scelta == "📩 Invia Richiesta":
        st.subheader("📅 Disponibilità e Prenotazione")
        st.info(f"Nota: puoi prenotare solo a partire da Lunedì {prossimo_lunedi.strftime('%d/%m')}")
        
        # Calendario compatto (stessa logica precedente)
        anno, mese = oggi.year, oggi.month
        nome_mese_it = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"][mese-1]
        cal = calendar.monthcalendar(anno, mese)
        limite_mese = 3
        if not df_limiti.empty:
            r_lim = df_limiti[df_limiti['Mese'].str.lower() == nome_mese_it.lower()]
            if not r_lim.empty: limite_mese = int(r_lim['Limite'].values[0])

        cols_h = st.columns(7)
        for i, g_n in enumerate(["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]): cols_h[i].write(f"**{g_n}**")
        
        for settimana in cal:
            cols = st.columns(7)
            for i, giorno in enumerate(settimana):
                if giorno != 0:
                    d_str = f"{anno}-{mese:02d}-{giorno:02d}"
                    is_bloccato = d_str in df_blocchi['Data'].astype(str).values
                    occ = df_richieste[df_richieste['Periodo'].astype(str) == d_str].shape[0]
                    if is_bloccato: ico = "🔒"
                    elif occ >= limite_mese: ico = "🔴"
                    elif occ == limite_mese - 1: ico = "🟡"
                    else: ico = "🟢"
                    cols[i].markdown(f"{giorno}<br>{ico}", unsafe_allow_html=True)

        st.divider()
        with st.form("richiesta_form"):
            t = st.selectbox("Tipo", ["Ferie", "ROL", "104", "Congedo"])
            p = st.date_input("Date", value=(), min_value=prossimo_lunedi)
            n = st.text_area("Note")
            if st.form_submit_button("INVIA"):
                if len(p) == 2:
                    giorni_r = pd.date_range(start=p[0], end=p[1])
                    esente = str(utente_info.get('SenzaLimiti', '0')) == "1"
                    possibile = True
                    for g in giorni_r:
                        if str(g.date()) in df_blocchi['Data'].astype(str).values:
                            st.error(f"❌ Il {g.date()} è un periodo bloccato."); possibile = False; break
                        occ_g = df_richieste[df_richieste['Periodo'].astype(str) == str(g.date())].shape[0]
                        if not esente and t in ["Ferie", "ROL"] and occ_g >= limite_mese:
                            st.error(f"❌ Il {g.date()} è completo!"); possibile = False; break
                    
                    if possibile:
                        nuove = [{"Data_Richiesta": oggi.strftime("%d/%m/%Y"), "Nome": st.session_state.utente_loggato, "Tipo": t, "Periodo": str(g.date()), "Note": n} for g in giorni_r]
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True))
                        invia_notifica_email(st.session_state.utente_loggato, t, str(p), n)
                        st.success("Inviata!"); st.balloons(); st.rerun()

    # --- ADMIN ---
    elif scelta == "⚙️ Admin":
        t1, t2, t3, t4, t5 = st.tabs(["MATRICE PROSSIMA SETT", "LIMITI", "UTENTI & RESET", "BLOCCHI PERIODI", "DB"])
        
        with t1: # Matrice Settimana Prossima
            st.subheader(f"Pianificazione dal {prossimo_lunedi.strftime('%d/%m')}")
            sett_prox = [prossimo_lunedi + timedelta(days=i) for i in range(7)]
            df_richieste['Data_G'] = pd.to_datetime(df_richieste['Periodo']).dt.date
            assenti = df_richieste[df_richieste['Data_G'].isin(sett_prox)]['Nome'].unique()
            if len(assenti) > 0:
                mat_data = []
                for d in sorted(assenti):
                    r = {"Dipendente": d}
                    for g in sett_prox:
                        r[g.strftime('%a %d/%m')] = df_richieste[(df_richieste['Nome'] == d) & (df_richieste['Data_G'] == g)]['Tipo'].values[0] if not df_richieste[(df_richieste['Nome'] == d) & (df_richieste['Data_G'] == g)].empty else "-"
                    mat_data.append(r)
                st.dataframe(pd.DataFrame(mat_data).set_index("Dipendente"), use_container_width=True)
            else: st.info("Nessuna prenotazione per la prossima settimana.")

        with t2: # Limiti (Stesso di prima)
            with st.form("lim"):
                nuovi = {r['Mese']: st.number_input(f"Limite {r['Mese']}", 1, 15, int(r['Limite'])) for i, r in df_limiti.iterrows()}
                if st.form_submit_button("Salva"):
                    conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi.items()), columns=['Mese', 'Limite'])); st.rerun()

        with t3: # Utenti + RESET PW
            st.write("**Reset Password a '12345'**")
            u_reset = st.selectbox("Seleziona utente da resettare", ["---"] + df_dip['Nome'].tolist())
            if st.button("RESETTA ORA"):
                if u_reset != "---":
                    idx = df_dip[df_dip['Nome'] == u_reset].index[0]
                    df_dip.at[idx, 'Password'] = "12345"; df_dip.at[idx, 'PrimoAccesso'] = "1"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success(f"Password di {u_reset} resettata!"); st.rerun()
            st.divider()
            # Aggiungi/Elimina (Spostati qui per spazio)
            with st.expander("Aggiungi Nuovo Dipendente"):
                with st.form("add"):
                    nn = st.text_input("Nome").upper(); cc = st.selectbox("Contratto", ["Fiduciario", "Armato", "Admin"]); ee = st.selectbox("Esenzione?", ["NO", "SI"])
                    if st.form_submit_button("Aggiungi"):
                        nuovo = {"Nome": nn, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": cc, "PrimoAccesso": "1", "SenzaLimiti": ("1" if ee == "SI" else "0")}
                        conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True)); st.rerun()

        with t4: # Blocco Periodi
            st.write("**Blocca date specifiche (es. 24 Dicembre)**")
            with st.form("block"):
                d_b = st.date_input("Data da bloccare")
                m_b = st.text_input("Motivo (es. Chiusura Aziendale)")
                if st.form_submit_button("BLOCCA DATA"):
                    nuovo_b = pd.DataFrame([{"Data": str(d_b), "Motivo": m_b}])
                    conn.update(worksheet="Blocchi", data=pd.concat([df_blocchi, nuovo_b], ignore_index=True))
                    st.rerun()
            st.write("**Date attualmente bloccate:**")
            st.dataframe(df_blocchi)
            if st.button("Svuota tutti i blocchi"):
                conn.update(worksheet="Blocchi", data=pd.DataFrame(columns=['Data', 'Motivo'])); st.rerun()

        with t5: st.dataframe(df_richieste)
