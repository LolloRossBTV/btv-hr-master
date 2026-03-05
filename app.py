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
    # Pulizia nomi e stringhe per evitare errori di confronto
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.upper().str.strip()
    df_dip['PrimoAccesso'] = df_dip['PrimoAccesso'].astype(str).str.strip()
except Exception as e:
    st.error(f"Errore caricamento database: {e}"); st.stop()

if "autenticato" not in st.session_state: st.session_state.autenticato = False
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None

st.title("🏥 Sistema Gestione Assenze")

# --- LOGIN ---
if not st.session_state.autenticato:
    with st.form("login"):
        user_list = df_dip['Nome_Display'].tolist()
        user = st.selectbox("Seleziona Nome", user_list)
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRA"):
            # Confronto robusto per la password
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
    dati_u = df_dip[df_dip['Nome_Display'] == nome_u].iloc[0]

    # --- CONTROLLO CAMBIO PASSWORD OBBLIGATORIO (CORRETTO) ---
    if dati_u['PrimoAccesso'] == "1":
        st.warning(f"⚠️ SICUREZZA: Cambio password obbligatorio per {nome_u}")
        with st.form("cambio_pw_obbligatorio"):
            nuova_pw = st.text_input("Inserisci nuova Password (min. 4 caratteri)", type="password")
            conferma_pw = st.text_input("Conferma nuova Password", type="password")
            
            if st.form_submit_button("AGGIORNA PASSWORD E ACCEDI"):
                if nuova_pw == conferma_pw and len(nuova_pw) >= 4:
                    # Identifica l'indice corretto nel DataFrame originale
                    idx = df_dip[df_dip['Nome_Display'] == nome_u].index[0]
                    
                    # Aggiorna i valori
                    df_dip.at[idx, 'Password'] = str(nuova_pw).strip()
                    df_dip.at[idx, 'PrimoAccesso'] = "0"
                    
                    # Prepara il salvataggio rimuovendo la colonna temporanea
                    df_salva = df_dip.drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_salva)
                    
                    st.success("✅ Password aggiornata con successo!")
                    st.balloons()
                    st.rerun()
                elif len(nuova_pw) < 4:
                    st.error("❌ La password deve essere lunga almeno 4 caratteri.")
                else:
                    st.error("❌ Le password non coincidono.")
        st.stop() # Impedisce di vedere il resto finché non cambia PW

    # --- CARICAMENTO ALTRE TABELLE ---
    try:
        df_richieste = conn.read(worksheet="Richieste", ttl="1m")
        df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
    except:
        df_limiti = pd.DataFrame(columns=['Mese', 'Limite'])

    # --- SIDEBAR E NAVIGAZIONE ---
    st.sidebar.success(f"👤 {nome_u}")
    menu = ["📊 Dashboard", "📩 Invia Richiesta"]
    if "ROSSINI" in nome_u.upper(): 
        menu.append("⚙️ Admin")
    scelta = st.sidebar.radio("Menu", menu)
    
    if st.sidebar.button("Logout"): 
        st.session_state.autenticato = False
        st.rerun()

    # --- CONTENUTI SEZIONI ---
    if scelta == "📊 Dashboard":
        c1, c2, c3 = st.columns(3)
        c1.metric("Ferie", f"{dati_u['Ferie']} gg")
        c2.metric("ROL", f"{dati_u['ROL']} ore")
        c3.metric("Contratto", dati_u['Contratto'])

    elif scelta == "📩 Invia Richiesta":
        with st.form("invio"):
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
                            st.error(f"Pieno il {g.date()} (Max {lim_g})"); possibile = False; break
                    if possibile:
                        nuove = [{"Data_Richiesta": datetime.now().strftime("%d/%m/%Y"), "Nome": nome_u, "Tipo": tipo, "Periodo": str(gx.date()), "Note": note} for gx in giorni]
                        conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove)], ignore_index=True))
                        invia_notifica_email(nome_u, tipo, f"{per[0]} - {per[1]}", note)
                        st.success("Richiesta inviata!"); st.balloons()

    elif scelta == "⚙️ Admin":
        t1, t2, t3, t4, t5 = st.tabs(["📅 MATRICE LUN-DOM", "🔢 LIMITI MENSILI", "➕ AGGIUNGI", "🗑️ ELIMINA", "📊 DB"])
        # ... (Resto del codice Admin invariato) ...
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
        with t2:
            if not df_limiti.empty:
                nuovi_l = {}
                c1, c2, c3 = st.columns(3)
                for i, r in df_limiti.iterrows():
                    with [c1, c2, c3][i % 3]:
                        nuovi_l[r['Mese']] = st.number_input(f"Limite {r['Mese']}", 1, 20, int(r['Limite']), key=f"l_{r['Mese']}")
                if st.button("Salva Limiti"):
                    conn.update(worksheet="Limiti_Mensili", data=pd.DataFrame(list(nuovi_l.items()), columns=['Mese', 'Limite']))
                    st.success("Salvati!"); st.rerun()
        with t3:
            with st.form("add"):
                nn = st.text_input("Nome e Cognome").upper()
                if st.form_submit_button("Aggiungi"):
                    n_u = {"Nome": nn, "Password": "12345", "Ferie": 0, "ROL": 0, "Contratto": "Fiduciario", "PrimoAccesso": "1"}
                    conn.update(worksheet="Dipendenti", data=pd.concat([df_dip.drop(columns=['Nome_Display']), pd.DataFrame([n_u])], ignore_index=True))
                    st.success(f"{nn} aggiunto!"); st.rerun()
        with t4:
            st.subheader("Rimuovi risorsa")
            da_eliminare = st.selectbox("Seleziona dipendente", ["---"] + df_dip['Nome'].tolist())
            if st.button("CONFERMA ELIMINAZIONE", type="primary"):
                if da_eliminare != "---":
                    df_up = df_dip[df_dip['Nome'] != da_eliminare].drop(columns=['Nome_Display'])
                    conn.update(worksheet="Dipendenti", data=df_up)
                    st.success(f"{da_eliminare} rimosso!"); st.rerun()
        with t5:
            st.dataframe(df_richieste)
