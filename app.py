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

# --- 2. FUNZIONE INVIO MAIL ---
def invia_notifica_email(utente, tipo, periodo, note):
    mittente = "tua_email@gmail.com" 
    password = "la_tua_app_password"
    destinatario = "ufficio_personale@esempio.it" 
    msg = MIMEMultipart()
    msg['From'] = mittente; msg['To'] = destinatario
    msg['Subject'] = f"RICHIESTA ASSENZA: {utente} - {tipo}"
    corpo = f"Nuova richiesta:\nDipendente: {utente}\nTipo: {tipo}\nPeriodo: {periodo}\nNote: {note}"
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
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.replace('.0', '', regex=False).str.strip()
    if 'SenzaLimiti' not in df_dip.columns: df_dip['SenzaLimiti'] = "0"
    df_dip['SenzaLimiti'] = df_dip['SenzaLimiti'].astype(str).str.replace('.0', '', regex=False).str.strip()
    
    df_richieste = conn.read(worksheet="Richieste", ttl=0)
    df_limiti = conn.read(worksheet="Limiti_Mensili", ttl=0)
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
                st.session_state.autenticato = True
                st.session_state.utente_loggato = u; st.rerun()
            else: st.error("Password errata!")

# --- 5. AREA RISERVATA ---
else:
    utente_info = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]
    
    # Cambio PW Obbligatorio
    if utente_info['PrimoAccesso'] == "1":
        with st.form("pw"):
            n1 = st.text_input("Nuova Password", type="password")
            n2 = st.text_input("Conferma", type="password")
            if st.form_submit_button("SALVA"):
                if n1 == n2 and len(n1) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = n1; df_dip.at[idx, 'PrimoAccesso'] = "0"
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success("Fatto!"); st.rerun()
        st.stop()

    # Sidebar
    st.sidebar.info(f"👤 {st.session_state.utente_loggato}")
    pagine = ["📊 Dashboard", "📩 Invia Richiesta"]
    if "ROSSINI" in st.session_state.utente_loggato.upper(): pagine.append("⚙️ Admin")
    scelta = st.sidebar.radio("Menu", pagine)
    if st.sidebar.button("Logout"): st.session_state.autenticato = False; st.rerun()

    # --- DASHBOARD ---
    if scelta == "📊 Dashboard":
        st.subheader("I tuoi contatori")
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie residue", f"{utente_info['Ferie']} gg")
        c2.metric("ROL residui", f"{utente_info['ROL']} ore")
        c3.metric("Contratto", utente_info['Contratto'])

    # --- INVIA RICHIESTA CON CALENDARIO COMPATTO ---
    elif scelta == "📩 Invia Richiesta":
        st.subheader("📅 Disponibilità Mensile")
        
        # Logica Calendario
        oggi = datetime.now()
        anno, mese = oggi.year, oggi.month
        nome_mese_it = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"][mese-1]
        
        st.write(f"**{nome_mese_it} {anno}** (🟢 <2 | 🟡 2 | 🔴 Pieno)")
        
        # Griglia Calendario
        giorni_settimana = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        cols = st.columns(7)
        for i, g_nome in enumerate(giorni_settimana):
            cols[i].write(f"**{g_nome}**")
        
        cal = calendar.monthcalendar(anno, mese)
        limite_mese = 3
        if not df_limiti.empty:
            r_lim = df_limiti[df_limiti['Mese'].str.lower() == nome_mese_it.lower()]
            if not r_lim.empty: limite_mese = int(r_lim['Limite'].values[0])

        for settimana in cal:
            cols = st.columns(7)
            for i, giorno in enumerate(settimana):
                if giorno == 0:
                    cols[i].write("")
                else:
                    data_str = f"{anno}-{mese:02d}-{giorno:02d}"
                    occ = df_richieste[df_richieste['Periodo'].astype(str) == data_str].shape[0]
                    
                    if occ >= limite_mese: ico = "🔴"
                    elif occ == limite_mese - 1: ico = "🟡"
                    else: ico = "🟢"
                    
                    cols[i].markdown(f"{giorno}<br>{ico}", unsafe_allow_html=True)

        st.divider()
        
        with st.form("richiesta_form"):
            t = st.selectbox("Cosa richiedi?", ["Ferie", "ROL", "104", "Congedo"])
            p = st.date_input("Seleziona Date", value=())
            n = st.text_area("Note (opzionale)")
            
            if st.form_submit_button("INVIA RICHIESTA"):
                if len(p) == 2:
                    giorni_r = pd.date_range(start=p[0], end=p[1])
                    esente = utente_info.get('SenzaLimiti', '0') == "1"
                    possibile = True
                    
                    if not esente:
                        for g in giorni_r:
                            occ_g = df_richieste[df_richieste['Periodo'].astype(str) == str(g.date())].shape[0]
                            if t in ["Ferie", "ROL"] and occ_g >= limite_mese:
                                st.error(f"❌ Il giorno {g.date()} è già completo!"); possibile = False; break
                    
                    if possibile:
                        nuove = []
                        for g in giorni_r:
                            nuove.append({"Data_Richiesta": oggi.strftime("%d/%m/%Y"), "Nome": st.session_state.utente_loggato, "Tipo": t, "Periodo": str(g.date()), "Note": n})
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True))
                        invia_notifica_email(st.session_state.utente_loggato, t, str(p), n)
                        st.success("Richiesta inviata!"); st.balloons(); st.rerun()
                else: st.warning("Seleziona Inizio e Fine.")

    # --- ADMIN ---
    elif scelta == "⚙️ Admin":
        t1, t2, t3, t4 = st.tabs(["MATRICE", "LIMITI", "GESTIONE UTENTI", "LOG RICHIESTE"])
        
        with t1:
            oggi_m = datetime.now().date()
            lun = oggi_m - timedelta(days=oggi_m.weekday())
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
            else: st.info("Tutti presenti questa settimana.")

        with t2:
            with st.form("lim_form"):
                nuovi = {}
                for idx, row in df_limiti.iterrows():
                    nuovi[row['Mese']] = st.number_input(f"Limite {row['Mese']}", 1, 15, int(row['Limite']))
                if st.form_submit_button("Salva"):
                    conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi.items()), columns=['Mese', 'Limite']))
                    st.success("Aggiornato!"); st.rerun()

        with t3:
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("**Aggiungi**")
                with st.form("add"):
                    nn = st.text_input("Nome").upper()
                    cc = st.selectbox("Contratto", ["Fiduciario", "Armato", "Admin"])
                    ee = st.selectbox("Esenzione?", ["NO", "SI"])
                    if st.form_submit_button("Aggiungi"):
                        f_e = "1" if ee == "SI" else "0"
                        nuovo = {"Nome": nn, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": cc, "PrimoAccesso": "1", "SenzaLimiti": f_e}
                        conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo])], ignore_index=True))
                        st.rerun()
            with col_b:
                st.write("**Elimina**")
                chi = st.selectbox("Chi?", ["---"] + df_dip['Nome'].tolist())
                if st.button("ELIMINA"):
                    conn.update(worksheet="Dipendenti", data=df_dip[df_dip['Nome'] != chi].drop(columns=['Nome_Display']))
                    st.rerun()

        with t4: st.dataframe(df_richieste)
