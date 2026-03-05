import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE E CONNESSIONE ---
st.set_page_config(page_title="Gestione BTV", layout="wide")
st.cache_data.clear() # Forza l'app a dimenticare i vecchi dati ogni volta che aggiorni

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. FUNZIONE INVIO MAIL ---
def invia_notifica_email(utente, tipo, periodo, note):
    mittente = "tua_email@gmail.com"  # <--- METTI LA TUA MAIL
    password = "la_tua_app_password"   # <--- METTI LA TUA PASSWORD APP
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
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_dip.columns = df_dip.columns.str.strip()
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()
    # Pulizia estrema del valore PrimoAccesso
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.replace('.0', '', regex=False).str.strip()
except Exception as e:
    st.error(f"Errore connessione Sheet: {e}")
    st.stop()

if "autenticato" not in st.session_state:
    st.session_state.autenticato = False
if "utente_loggato" not in st.session_state:
    st.session_state.utente_loggato = None

st.title("🏥 Sistema Presenze BTV")

# --- 4. LOGICA LOGIN ---
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
    # Recupero dati dell'utente loggato
    utente_info = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].iloc[0]
    
    # --- CONTROLLO CAMBIO PW OBBLIGATORIO ---
    if utente_info['PrimoAccesso'] == "1":
        st.warning(f"⚠️ SICUREZZA: {st.session_state.utente_loggato}, devi cambiare la password.")
        with st.form("cambio_obbligatorio"):
            n1 = st.text_input("Nuova Password", type="password")
            n2 = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA E ACCEDI"):
                if n1 == n2 and len(n1) >= 4:
                    idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                    df_dip.at[idx, 'Password'] = n1
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    # Salvataggio su Google
                    conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                    st.success("Password aggiornata!")
                    st.rerun()
                else:
                    st.error("Le password non coincidono o sono troppo corte.")
        st.stop() # Blocca tutto il resto

    # --- CARICAMENTO ALTRE TABELLE ---
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl=0)
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl=0)
    except:
        df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    # --- NAVIGAZIONE SIDEBAR ---
    st.sidebar.info(f"👤 {st.session_state.utente_loggato}")
    elif scelta == "📩 Invia Richiesta":
        with st.form("richiesta_form"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL", "104", "Congedo"])
            periodo = st.date_input("Date", value=())
            note = st.text_area("Note")
            if st.form_submit_button("Invia"):
                if len(periodo) == 2:
                    giorni = pd.date_range(start=periodo[0], end=periodo[1])
                    
                    # --- CONTROLLO ESENZIONE LIMITI ---
                    esente = str(utente_info.get('SenzaLimiti', '0')).strip() == "1"
                    
                    possibile = True
                    if not esente:
                        for g in giorni:
                            mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
                            m_n = mesi_it[g.month - 1]
                            lim_g = 3
                            if not df_limiti.empty:
                                r_l = df_limiti[df_limiti['Mese'].str.lower() == m_n.lower()]
                                if not r_l.empty: lim_g = int(r_l['Limite'].values[0])
                            
                            occ = df_richieste[df_richieste['Periodo'].astype(str) == str(g.date())].shape[0]
                            if tipo in ["Ferie", "ROL"] and occ >= lim_g:
                                st.error(f"Giorno {g.date()} completo (Max {lim_g} persone)."); possibile = False; break
                    
                    if possibile:
                        nuove_richieste = []
                        for g in giorni:
                            nuove_richieste.append({
                                "Data_Richiesta": datetime.now().strftime("%d/%m/%Y"),
                                "Nome": st.session_state.utente_loggato,
                                "Tipo": tipo,
                                "Periodo": str(g.date()),
                                "Note": note
                            })
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove_richieste)], ignore_index=True))
                        invia_notifica_email(st.session_state.utente_loggato, tipo, str(periodo), note)
                        st.success("Richiesta inviata correttamente!"); st.balloons()
        with st.form("richiesta_form"):
            tipo = st.selectbox("Tipo", ["Ferie", "ROL", "104", "Congedo"])
            periodo = st.date_input("Date", value=())
            note = st.text_area("Note")
           with t3: # Aggiungi Dipendente
            with st.form("add_dip"):
                n_nome = st.text_input("Nome e Cognome").upper()
                n_cont = st.selectbox("Contratto", ["Fiduciario", "Armato", "Admin"])
                # NUOVO: Selettore per esenzione limiti
                n_esente = st.selectbox("Esenzione Limiti Prenotazione", ["NO (Soggetto a limiti)", "SI (Senza limiti)"])
                
                if st.form_submit_button("Registra Dipendente"):
                    if n_nome:
                        # Convertiamo la scelta in 0 o 1
                        val_esente = "1" if "SI" in n_esente else "0"
                        
                        nuovo_d = {
                            "Nome": n_nome, 
                            "Password": "12345", 
                            "Ferie": 0, 
                            "ROL": 0, 
                            "Contratto": n_cont, 
                            "PrimoAccesso": "1",
                            "SenzaLimiti": val_esente  # Salva il flag nel foglio
                        }
                        
                        df_nuovo = pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo_d])], ignore_index=True)
                        conn.update(worksheet="Dipendenti", data=df_agg_f)
                        st.success(f"✅ {n_nome} aggiunto correttamente!"); st.rerun()
                    else:
                        st.error("Inserisci un nome!")
                            "Tipo": tipo,
                            "Periodo": str(g.date()),
                            "Note": note
                        })
                    conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove_richieste)], ignore_index=True))
                    invia_notifica_email(st.session_state.utente_loggato, tipo, str(periodo), note)
                    st.success("Richiesta inviata correttamente!"); st.balloons()

    elif scelta == "⚙️ Admin":
        t1, t2, t3, t4, t5 = st.tabs(["MATRICE", "LIMITI", "AGGIUNGI", "ELIMINA", "DB"])
        
        with t1: # Matrice Settimanale
            oggi = datetime.now().date()
            lun = oggi - timedelta(days=oggi.weekday())
            settimana = [lun + timedelta(days=i) for i in range(7)]
            df_richieste['Data_G'] = pd.to_datetime(df_richieste['Periodo']).dt.date
            assenti = df_richieste[df_richieste['Data_G'].isin(settimana)]['Nome'].unique()
            if len(assenti) > 0:
                matrice_dati = []
                for d in sorted(assenti):
                    r_mat = {"Dipendente": d}
                    for g in settimana:
                        c_nome = g.strftime('%a %d/%m')
                        m = df_richieste[(df_richieste['Nome'] == d) & (df_richieste['Data_G'] == g)]
                        r_mat[c_nome] = m['Tipo'].values[0] if not m.empty else "-"
                    matrice_dati.append(r_mat)
                st.dataframe(pd.DataFrame(matrice_dati).set_index("Dipendente"), use_container_width=True)
            else: st.info("Tutti presenti questa settimana.")

        with t2: # Limiti Mensili
            with st.form("limiti_form"):
                nuovi_lim = {}
                for i, r in df_limiti.iterrows():
                    nuovi_lim[r['Mese']] = st.number_input(f"Limite {r['Mese']}", 1, 10, int(r['Limite']))
                if st.form_submit_button("Salva Limiti"):
                    conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi_lim.items()), columns=['Mese', 'Limite']))
                    st.success("Limiti aggiornati!"); st.rerun()

        with t3: # Aggiungi Dipendente
            with st.form("add_dip"):
                n_nome = st.text_input("Nome e Cognome").upper()
                n_cont = st.selectbox("Contratto", ["Fiduciario", "Armato", "Admin"])
                if st.form_submit_button("Aggiungi"):
                    nuovo_d = {"Nome": n_nome, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": n_cont, "PrimoAccesso": "1"}
                    conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([nuovo_d])], ignore_index=True))
                    st.success("Dipendente aggiunto!"); st.rerun()

        with t4: # Elimina Dipendente
            da_eliminare = st.selectbox("Chi vuoi eliminare?", ["---"] + df_dip['Nome'].tolist())
            if st.button("ELIMINA DEFINITIVAMENTE", type="primary"):
                if da_eliminare != "---":
                    df_agg = df_dip[df_dip['Nome'] != da_eliminare].drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_agg)
                    st.success(f"{da_eliminare} eliminato!"); st.rerun()

        with t5: # Database grezzo
            st.dataframe(df_richieste)
