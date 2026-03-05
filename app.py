import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="Portale Gestionale BTV", layout="centered")

if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None
if 'cambio_obbligatorio' not in st.session_state:
    st.session_state.cambio_obbligatorio = False

# --- 2. MOTORE EMAIL ---
def send_email(subject, body):
    try:
        creds = st.secrets["emails"]
        msg = MIMEMultipart()
        msg['From'] = creds["sender_email"]
        msg['To'] = creds["receiver_email"]
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(creds["smtp_server"], int(creds["smtp_port"]))
        server.starttls()
        pwd = str(creds["sender_password"]).replace(" ", "").strip()
        server.login(creds["sender_email"], pwd)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Errore Email: {e}")
        return False

# --- 3. CARICAMENTO DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0).dropna(subset=['Nome'])
    df_dip['Nome_Display'] = df_dip['Nome'].astype(str).str.strip()
except Exception as e:
    st.error(f"❌ Errore Database: {e}")
    st.stop()

# --- 4. ACCESSO E SICUREZZA ---
if not st.session_state.autenticato:
    if st.session_state.cambio_obbligatorio:
        st.title("🔑 Cambio Password Obbligatorio")
        st.warning(f"Profilo: {st.session_state.utente_loggato}")
        
        n_p = st.text_input("Nuova Password (min. 5 car.)", type="password", key="np_new")
        c_p = st.text_input("Conferma Password", type="password", key="cp_new")
        
        if st.button("Salva e Accedi"):
            if n_p == c_p and len(n_p) >= 5:
                idx = df_dip[df_dip['Nome_Display'] == st.session_state.utente_loggato].index[0]
                df_dip.at[idx, 'Password'] = n_p
                df_dip.at[idx, 'PrimoAccesso'] = 'FALSE' # Scrive FALSE per i prossimi accessi
                conn.update(worksheet="Dipendenti", data=df_dip.drop(columns=['Nome_Display']))
                st.session_state.cambio_obbligatorio = False
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password non valide.")
        st.stop()

    st.title("🛡️ Accesso BTV")
    u_scelto = st.selectbox("DIPENDENTE", ["--- Seleziona ---"] + sorted(df_dip['Nome_Display'].unique()))
    p_in = st.text_input("PASSWORD", type="password")
    
    if st.button("Entra"):
        if u_scelto != "--- Seleziona ---":
            idx = df_dip[df_dip['Nome_Display'] == u_scelto].index[0]
            row = df_dip.iloc[idx]
            pw_db = str(row['Password']).split('.')[0].strip()
            
            if str(p_in).strip() == pw_db:
                st.session_state.utente_loggato = str(row['Nome_Display'])
                
                # CORREZIONE: Legge 1, 1.0 o TRUE come primo accesso
                valore_primo = str(row['PrimoAccesso']).strip().upper()
                if valore_primo in ['1', '1.0', 'TRUE', 'SÌ']:
                    st.session_state.cambio_obbligatorio = True
                else:
                    st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password errata")
    st.stop()
# --- 5. AREA PRIVATA ---
else:
    nome_u = str(st.session_state.utente_loggato)
    st.sidebar.success(f"👤 {nome_u}")
    
    menu = ["I miei Saldi", "Invia Richiesta"]
    if "ROSSINI" in nome_u.upper():
        menu.append("Pannello Admin")
    
    scelta = st.sidebar.selectbox("Navigazione", menu)
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()
# --- 5. AREA PRIVATA ---
    else:
        nome_u = str(st.session_state.utente_loggato)
        st.sidebar.success(f"👤 {nome_u}")
        
        # CARICAMENTO DATI GLOBALE (Risolve il NameError in Admin)
        try:
            # Usiamo ttl="1m" per evitare il blocco Quota Exceeded visto nelle tue foto
            df_richieste = conn.read(worksheet="Richieste", ttl="1m")
            df_limiti = conn.read(worksheet="Limiti_Mensili", ttl="1m")
        except Exception as e:
            st.error(f"⚠️ Errore di connessione al database: {e}")
            st.stop()
        
        menu = ["📊 Dashboard Saldi", "📩 Invia Richiesta"]
        if "ROSSINI" in nome_u.upper(): 
            menu.append("⚙️ Pannello Admin")
        
        scelta = st.sidebar.radio("Navigazione", menu)
        
        if st.sidebar.button("Esci / Logout"):
            st.session_state.autenticato = False
            st.rerun()

        # --- SEZIONE SALDI ---
        if "Saldi" in scelta:
            st.header("📊 La tua situazione")
            dati_u = df_dip[df_dip['Nome_Display'] == nome_u].iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Ferie residue", f"{dati_u['Ferie']} gg")
            c2.metric("ROL residui", f"{dati_u['ROL']} ore")
            c3.metric("Tipo Contratto", dati_u['Contratto'])

        # --- SEZIONE INVIO RICHIESTA (GESTIONE PERIODO) ---
        elif "Richiesta" in scelta:
            st.header("📩 Inserisci Richiesta Periodo")
            with st.form("form_periodo", clear_on_submit=True):
                tipo = st.selectbox("Causale", ["Ferie", "ROL", "Legge 104", "Congedo Parentale"])
                periodo_scelto = st.date_input("Seleziona il periodo (Inizio e Fine)", value=())
                note = st.text_area("Note aggiuntive")
                
                if st.form_submit_button("🚀 Verifica e Invia"):
                    if len(periodo_scelto) == 2:
                        data_inizio, data_fine = periodo_scelto
                        giorni_richiesti = pd.date_range(start=data_inizio, end=data_fine)
                        
                        errore_limite = False
                        mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

                        for giorno in giorni_richiesti:
                            nome_mese = mesi_it[giorno.month - 1]
                            riga_lim = df_limiti[df_limiti['Mese'] == nome_mese]
                            lim_max = int(riga_lim['Limite'].values[0]) if not riga_lim.empty else 3
                            occupati = df_richieste[df_richieste['Periodo'].astype(str) == str(giorno.date())].shape[0]
                            
                            if tipo in ["Ferie", "ROL"] and occupati >= lim_max:
                                errore_limite = True; st.error(f"❌ Giorno {giorno.strftime('%d/%m')} pieno!"); break
                        
                        if not errore_limite:
                            nuove_righe = [{"Data_Richiesta": pd.Timestamp.now().strftime("%d/%m/%Y"), "Nome": nome_u, "Tipo": tipo, "Periodo": str(g.date()), "Note": note} for g in giorni_richiesti]
                            conn.update(worksheet="Richieste", data=pd.concat([df_richieste, pd.DataFrame(nuove_righe)], ignore_index=True))
                            st.success("✅ Periodo salvato!"); st.balloons()
                    else: st.warning("⚠️ Seleziona Inizio e Fine nel calendario.")

       # --- PANNELLO ADMIN (VISTA SETTIMANALE) ---
        elif "Admin" in scelta:
            st.header("⚙️ Pannello Amministratore")
            
            # Creiamo i Tab, mettendo la Pianificazione come primo
            t_pianif, t_lim, t_pers, t_db = st.tabs([
                "📅 PIANIFICAZIONE ODS", 
                "🔢 LIMITI MENSILI", 
                "👥 PERSONALE", 
                "📊 DATABASE"
            ])

            with t_pianif:
                st.subheader("🗓️ Assenze della Settimana (Prossimi 7 giorni)")
                
                # Calcoliamo l'intervallo temporale
                oggi = pd.Timestamp.now().date()
                fra_una_settimana = oggi + pd.Timedelta(days=7)
                
                # Filtriamo le richieste nel lasso temporale
                try:
                    # Assicuriamoci che la colonna Periodo sia in formato data
                    df_richieste['Data_Giorno'] = pd.to_datetime(df_richieste['Periodo']).dt.date
                    df_settimana = df_richieste[
                        (df_richieste['Data_Giorno'] >= oggi) & 
                        (df_richieste['Data_Giorno'] <= fra_una_settimana)
                    ].copy()

                    if not df_settimana.empty:
                        # Ordiniamo per data per facilitare l'ODS
                        df_settimana = df_settimana.sort_values(by='Data_Giorno')
                        
                        # Formattiamo la data per una lettura più "simpatica"
                        df_settimana['Giorno'] = df_settimana['Data_Giorno'].apply(lambda x: x.strftime('%A %d/%m'))
                        
                        # Mostriamo la tabella pulita
                        st.table(df_settimana[['Giorno', 'Nome', 'Tipo', 'Note']])
                    else:
                        st.info("✅ Nessuna assenza pianificata per i prossimi 7 giorni.")
                except Exception as e:
                    st.error(f"Errore nel filtro pianificazione: {e}")

            with t_lim:
                st.subheader("Modifica Soglie Assenze")
                nuovi_v = {}
                c1, c2, c3 = st.columns(3)
                for i, riga in df_limiti.iterrows():
                    m = riga['Mese']
                    with [c1, c2, c3][i % 3]:
                        nuovi_v[m] = st.number_input(f"{m.capitalize()}", 1, 15, int(riga['Limite']), key=f"lim_{m}")
                
                if st.button("💾 SALVA LIMITI", use_container_width=True, type="primary"):
                    df_up = pd.DataFrame(list(nuovi_v.items()), columns=['Mese', 'Limite'])
                    conn.update(worksheet="Limiti_Mensili", data=df_up)
                    st.success("✅ Limiti aggiornati!"); st.rerun()

            with t_pers:
                st.write("**Gestione Rapida Dipendenti**")
                u_del = st.selectbox("Seleziona chi eliminare:", ["---"] + sorted(df_dip['Nome_Display'].unique()))
                if u_del != "---" and st.button("ELIMINA DEFINITIVAMENTE"):
                    conn.update(worksheet="Dipendenti", data=df_dip[df_dip['Nome_Display'] != u_del].drop(columns=['Nome_Display']))
                    st.success(f"Rimosso!"); st.rerun()

            with t_db:
                st.write("### Database Completo Richieste")
                st.dataframe(df_richieste, use_container_width=True)# Ora df_richieste è definito e non darà più errore!
                st.dataframe(df_richieste, use_container_width=True)
