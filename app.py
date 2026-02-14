import streamlit as st
import pandas as pd
import os
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
import time

# ==============================================================================
# 1. CONFIGURAZIONE E COSTANTI DI SISTEMA (PARAMETRI FISSI)
# ==============================================================================
# Definizione dei nomi file per il database CSV
FILE_DIPENDENTI = 'db_dipendenti.csv'
FILE_FERIE      = 'db_ferie.csv'
FILE_CONFIG     = 'db_config.csv'

# Credenziali amministrative predefinite
PASSWORD_ADMIN  = "admin2024"

# ------------------------------------------------------------------------------
# PARAMETRI DI MATURAZIONE MENSILE (Specifiche Contrattuali 2026)
# ------------------------------------------------------------------------------
# Valori per contratto tipo GUARDIA
MAT_FERIE_GUARDIA    = 1.917

# Valori per contratto tipo FIDUCIARIO
MAT_FERIE_FIDUCIARIO = 2.16 
MAT_ROL_FIDUCIARIO   = 0.60   


# ==============================================================================
# 2. FUNZIONI DI SISTEMA (NOTIFICHE E CONFIGURAZIONE)
# ==============================================================================
def invia_email(oggetto, corpo):
    """
    Gestisce l'invio delle notifiche via email utilizzando Streamlit Secrets.
    """
    try:
        if "email" not in st.secrets:
            return False
            
        msg = MIMEText(corpo)
        msg['Subject'] = oggetto
        msg['From'] = st.secrets["email"]["user"]
        msg['To'] = st.secrets["email"]["admin_email"]
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(st.secrets["email"]["user"], st.secrets["email"]["password"])
            server.sendmail(st.secrets["email"]["user"], [msg['To']], msg.as_string())
        return True
    except Exception as e:
        return False


def carica_config():
    """
    Carica o inizializza il file di configurazione per il controllo dei limiti.
    """
    if not os.path.exists(FILE_CONFIG):
        # Forza l'aggiornamento iniziale impostando il mese precedente
        mese_scorso = (datetime.now().month - 1) if datetime.now().month > 1 else 12
        pd.DataFrame([{"limite": 3, "ultimo_mese": mese_scorso}]).to_csv(FILE_CONFIG, index=False)
    
    config_df = pd.read_csv(FILE_CONFIG)
    
    # Verifica integrità della struttura del file config
    if 'ultimo_mese' not in config_df.columns:
        config_df['ultimo_mese'] = datetime.now().month
        config_df.to_csv(FILE_CONFIG, index=False)
        
    return config_df.iloc[0]


def salva_config(nuovo_limite, nuovo_mese):
    """
    Aggiorna i parametri di configurazione nel file CSV.
    """
    pd.DataFrame([{"limite": nuovo_limite, "ultimo_mese": nuovo_mese}]).to_csv(FILE_CONFIG, index=False)


# ==============================================================================
# 3. LOGICA DI CALCOLO MATURAZIONE (GUARDIE vs FIDUCIARI)
# ==============================================================================
def applica_maturazione(df_dip):
    """
    Aggiunge i ratei mensili distinguendo tra i contratti Guardie e Fiduciari.
    """
    for idx, row in df_dip.iterrows():
        # Logica specifica per contratto GUARDIA
        if row['Contratto'] == "Guardia":
            df_dip.at[idx, 'Ferie'] += MAT_FERIE_GUARDIA
        
        # Logica specifica per contratto FIDUCIARIO
        else:
            df_dip.at[idx, 'Ferie'] += MAT_FERIE_FIDUCIARIO
            df_dip.at[idx, 'ROL'] += MAT_ROL_FIDUCIARIO
            
    return df_dip


def aggiorna_maturazioni_mensili(df_dip, config):
    """
    Esegue il controllo automatico del cambio mese per l'aggiornamento dei saldi.
    """
    oggi = datetime.now()
    
    try:
        ultimo_registrato = int(config['ultimo_mese'])
    except:
        ultimo_registrato = oggi.month

    # Se il mese corrente è diverso dall'ultimo registrato (es. Febbraio != Gennaio)
    if oggi.month != ultimo_registrato:
        st.info(f"🔄 Rilevato cambio mese: {oggi.strftime('%B %Y')}. Aggiornamento saldi in corso...")
        
        df_dip = applica_maturazione(df_dip)
        
        # Salvataggio dati e aggiornamento dello stato
        df_dip.to_csv(FILE_DIPENDENTI, index=False)
        salva_config(config['limite'], oggi.month)
        
        st.success("Maturazione mensile completata!")
        time.sleep(1)
        st.rerun()
        
    return df_dip


# ==============================================================================
# 4. INIZIALIZZAZIONE DATABASE (ANAGRAFICA ESTESA 42 RECORD)
# ==============================================================================
def inizializza_database():
    """
    Crea o carica i file CSV necessari con l'anagrafica completa dei dipendenti.
    """
    # Elenco completo originale comprensivo di saldi iniziali
    elenco = [
        ["BOZZI RAFFAELLA", 258.08, 106.6, "Fiduciario", "12345", True, False],
        ["LAMADDALENA ANTONIO", 47.31, 0, "Guardia", "12345", True, False],
        ["BUQUICCHIO ANGELA", 259.03, 48.65, "Fiduciario", "12345", True, False],
        ["FIORE ANTONIO", 39.55, 0, "Guardia", "12345", True, False],
        ["PALTERA CRISTINA", 227.03, 48.65, "Fiduciario", "12345", True, False],
        ["VISTA NICOLA", 207.03, 45.6, "Fiduciario", "12345", True, False],
        ["SISTO FEDERICA", 193.91, 50.65, "Fiduciario", "12345", True, False],
        ["MANGIONE FRANCESCO", 200.25, 43.98, "Fiduciario", "12345", True, False],
        ["LOBASCIO MICHELE", 34.04, 0, "Guardia", "12345", True, False],
        ["BERGAMASCO COSIMO DAMIANO", 186.6, 47.81, "Fiduciario", "12345", True, False],
        ["GENTILE SAVERIO", 202.77, 25.62, "Fiduciario", "12345", True, False],
        ["MILILLO GENNARO", 32.60, 0, "Guardia", "12345", True, False],
        ["GIANNINI CAMILLA", 135.33, 85.08, "Fiduciario", "12345", True, False],
        ["PALERMO DOMENICO", 167.08, 48.01, "Fiduciario", "12345", True, False],
        ["MOSCA SIMONA", 166.51, 47.68, "Fiduciario", "12345", True, False],
        ["ACQUAVIVA ANNALISA", 126.4, 72.63, "Fiduciario", "12345", True, False],
        ["DILISO CLARA ANNARITA", 152.13, 44.23, "Fiduciario", "12345", True, False],
        ["ANTONACCI MARIO", 146.92, 43.98, "Fiduciario", "12345", True, False],
        ["MENGA LEONARDO", 174.0, 16.0, "Fiduciario", "12345", True, False],
        ["DI RELLA COSIMO DAMIANO", 153.41, 29.01, "Fiduciario", "12345", True, False],
        ["RANA DONATO", 146.41, 30.98, "Fiduciario", "12345", True, False],
        ["DI BARI GIORGIA", 112.76, 54.03, "Fiduciario", "12345", True, False],
        ["RAFASCHIERI ANNA ILENIA", 117.30, 32.73, "Fiduciario", "12345", True, False],
        ["BOTTALICO LEONARDO", 133.42, 9.33, "Fiduciario", "12345", True, False],
        ["DE NAPOLI SERENA", 26.49, 115.55, "Fiduciario", "12345", True, False],
        ["CAMPANILE DENNIS", 92.73, 47.85, "Fiduciario", "12345", True, False],
        ["MASTRONARDI ANNA GUENDALINA", 100.91, 27.15, "Fiduciario", "12345", True, False],
        ["ZIFARELLI ROBERTA", 72.96, 44.11, "Fiduciario", "12345", True, False],
        ["CARBONE ROBERTA", 66.64, 47.2, "Fiduciario", "12345", True, False],
        ["TRENTADUE ANNARITA", 65.95, 47.2, "Fiduciario", "12345", True, False],
        ["RENNA GIUSEPPE", 14.81, 0, "Guardia", "12345", True, False],
        ["MARTINO ALESSANDRO", 79.83, 21.12, "Fiduciario", "12345", True, False],
        ["GIORDANO DOMENICA ANNAMARIA", 53.37, 46.18, "Fiduciario", "12345", True, False],
        ["FUCCI LUCIA", 59.39, 26.15, "Fiduciario", "12345", True, False],
        ["CINQUEPALMI NICOLANTONIO", 53.69, 30.83, "Fiduciario", "12345", True, False],
        ["CISTERNINO BENITO", 93.14, -19.35, "Fiduciario", "12345", True, False],
        ["ABBATICCHIO ANTONIO", 53.13, 11.24, "Fiduciario", "12345", True, False],
        ["SANO' MORENA", 39.81, 24.0, "Fiduciario", "12345", True, False],
        ["CACUCCIOLO ROBERTA NICOLETTA", -33.95, 95.95, "Fiduciario", "12345", True, False],
        ["ROSSINI LORENZO", 6.40, 0, "Guardia", "12345", True, False],
        ["PORCARO NICOLA", 3.10, 0.64, "Fiduciario", "12345", True, False],
        ["TANGARI FRANCESCO", -39.85, 6.91, "Fiduciario", "12345", True, False]
    ]
    
    cols = ['Nome','Ferie','ROL','Contratto','Password','PrimoAccesso','Escluso']
    
    if not os.path.exists(FILE_DIPENDENTI):
        pd.DataFrame(elenco, columns=cols).to_csv(FILE_DIPENDENTI, index=False)
    else:
        df_e = pd.read_csv(FILE_DIPENDENTI)
        # Sincronizzazione colonne mancanti (Retrocompatibilità)
        for col in cols:
            if col not in df_e.columns:
                df_e[col] = False if col == 'Escluso' else (True if col == 'PrimoAccesso' else "12345")
        df_e.to_csv(FILE_DIPENDENTI, index=False)
            
    if not os.path.exists(FILE_FERIE):
        pd.DataFrame(columns=['Nome','Inizio','Fine','Tipo','Risorsa','Valore','Unita']).to_csv(FILE_FERIE, index=False)
    
    return pd.read_csv(FILE_DIPENDENTI), pd.read_csv(FILE_FERIE)


# ==============================================================================
# 5. LOGICA DI AUTENTICAZIONE (SISTEMA MULTI-RUOLO)
# ==============================================================================
st.set_page_config(page_title="Battistolli HR Master v57.1", layout="wide")
df_dip, df_ferie = inizializza_database()
config = carica_config()
df_dip = aggiorna_maturazioni_mensili(df_dip, config)

# CSS Personalizzato per migliorare la leggibilità (Struttura estesa)
st.markdown("""
    <style>
    .metric-container { background-color: #f1f3f5; border: 1px solid #ced4da; padding: 20px; border-radius: 12px; }
    .stMetric { color: #212529; }
    .stButton>button { width: 100%; border-radius: 6px; height: 3em; }
    .stExpander { border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# INTERFACCIA DI LOGIN
# ------------------------------------------------------------------------------
if "user" not in st.session_state:
    st.title("🏢 Gestione Personale Battistolli")
    st.subheader("Accedi al portale O.D.S.")
    
    login_col1, login_col2 = st.columns([1,1])
    
    with login_col1:
        u_in = st.text_input("COGNOME NOME").strip().upper()
        p_in = st.text_input("PASSWORD", type="password").strip()
        
        if st.button("ACCEDI AL SISTEMA"):
            # Controllo credenziali Admin
            if u_in == "ADMIN" and p_in == PASSWORD_ADMIN:
                st.session_state["user"] = "admin"
                st.rerun()
            
            # Controllo credenziali Dipendente (Fiduciari/Guardie)
            input_set = set(u_in.split())
            for idx, row in df_dip.iterrows():
                db_name_set = set(str(row['Nome']).upper().split())
                if input_set == db_name_set and str(row['Password']) == p_in:
                    st.session_state["user"] = row['Nome']
                    st.session_state["primo_accesso"] = row['PrimoAccesso']
                    st.rerun()
                    
            st.error("Dati non validi. Contattare l'ufficio HR.")
    st.stop()


user = st.session_state["user"]


# ==============================================================================
# 6. AREA AMMINISTRATORE (MODULO HR & GESTIONE ORGANICO)
# ==============================================================================
if user == "admin":
    st.header("👨‍💼 Pannello di Gestione HR")
    
    tabs = st.tabs(["Registro Richieste", "Gestione Personale", "Configurazione Sistema"])
    
    # --------------------------------------------------------------------------
    # TAB 1: MONITORAGGIO RICHIESTE
    # --------------------------------------------------------------------------
    with tabs[0]:
        st.subheader("Tutte le richieste inoltrate")
        st.dataframe(df_ferie, use_container_width=True)
        
        if st.button("Logout Amministratore"):
            del st.session_state["user"]
            st.rerun()
            
    # --------------------------------------------------------------------------
    # TAB 2: ANAGRAFICA E GESTIONE ORGANICO
    # --------------------------------------------------------------------------
    with tabs[1]:
        col_main, col_side = st.columns([2, 1])
        
        with col_main:
            st.subheader("1. Modifica Saldi e Contratti")
            st.caption("Nota: Le modifiche ai saldi sono immediate.")
            
            df_editor = st.data_editor(
                df_dip[['Nome', 'Contratto', 'Escluso', 'Ferie', 'ROL']],
                column_config={
                    "Contratto": st.column_config.SelectboxColumn("Contratto", options=["Fiduciario", "Guardia"]),
                    "Escluso": st.column_config.CheckboxColumn("Escluso Limiti", default=False),
                    "Ferie": st.column_config.NumberColumn("Ferie (GG)", format="%.2f"),
                    "ROL": st.column_config.NumberColumn("ROL (GG)", format="%.2f")
                },
                disabled=["Nome"], 
                use_container_width=True, 
                key="admin_master_editor"
            )
            
            if st.button("💾 SALVA MODIFICHE ANAGRAFICA"):
                df_dip.update(df_editor)
                df_dip.to_csv(FILE_DIPENDENTI, index=False)
                st.success("Database aggiornato!")
                time.sleep(0.5)
                st.rerun()

        with col_side:
            st.subheader("2. Operazioni Organico")
            
            # Funzione per l'assunzione di nuove Guardie o Fiduciari
            with st.expander("🆕 Nuova Assunzione"):
                new_n = st.text_input("Cognome Nome").upper().strip()
                new_t = st.selectbox("Tipo Contratto", ["Fiduciario", "Guardia"])
                new_f = st.number_input("Saldo Ferie Iniziale", value=0.0)
                new_r = st.number_input("Saldo ROL Iniziale", value=0.0)
                
                if st.button("CONFERMA ASSUNZIONE"):
                    if new_n and new_n not in df_dip['Nome'].values:
                        nuovo_record = pd.DataFrame([[new_n, new_f, new_r, new_t, "12345", True, False]], columns=df_dip.columns)
                        nuovo_record.to_csv(FILE_DIPENDENTI, mode='a', header=False, index=False)
                        st.success(f"Dipendente {new_n} inserito!"); time.sleep(1); st.rerun()
            
            # Funzione per rimuovere personale cessato
            with st.expander("🗑️ Cessazione Rapporto"):
                u_to_del = st.selectbox("Seleziona dipendente in uscita", df_dip['Nome'].unique())
                st.error("Attenzione: l'operazione è definitiva.")
                if st.button("ELIMINA DIPENDENTE"):
                    df_dip = df_dip[df_dip['Nome'] != u_to_del]
                    df_ferie = df_ferie[df_ferie['Nome'] != u_to_del]
                    df_dip.to_csv(FILE_DIPENDENTI, index=False)
                    df_ferie.to_csv(FILE_FERIE, index=False)
                    st.success(f"Archivio di {u_to_del} rimosso."); time.sleep(1); st.rerun()

            # Reset Password (torna a 12345)
            with st.expander("🔑 Reset Password"):
                u_reset = st.selectbox("Utente che ha perso la password", df_dip['Nome'].unique())
                if st.button("EFFETTUA RESET"):
                    df_dip.loc[df_dip['Nome'] == u_reset, ["Password", "PrimoAccesso"]] = ["12345", True]
                    df_dip.to_csv(FILE_DIPENDENTI, index=False)
                    st.success("Password resettata a 12345!"); time.sleep(1); st.rerun()

    # --------------------------------------------------------------------------
    # TAB 3: IMPOSTAZIONI AVANZATE
    # --------------------------------------------------------------------------
    with tabs[2]:
        st.subheader("Parametri Operativi")
        nuova_soglia = st.slider("Limite assenze operative (Pallini)", 1, 15, int(config['limite']))
        
        if st.button("Aggiorna Soglia"):
            salva_config(nuova_soglia, config['ultimo_mese'])
            st.success("Limite aggiornato!")
            st.rerun()
            
        st.divider()
        st.subheader("Azioni di Emergenza")
        if st.button("🔄 FORZA MATURAZIONE ORA (Tutti i contratti)"):
            df_dip = applica_maturazione(df_dip)
            df_dip.to_csv(FILE_DIPENDENTI, index=False)
            salva_config(config['limite'], datetime.now().month)
            st.success("Ratei mensili applicati correttamente!"); time.sleep(1); st.rerun()


# ==============================================================================
# 7. AREA UTENTE (GUARDIE E FIDUCIARI)
# ==============================================================================
else:
    # Gestione Cambio Password Obbligatorio
    if st.session_state.get("primo_accesso", False):
        st.warning("🔒 Benvenuto! Per la tua sicurezza, imposta una password personale.")
        pwd_1 = st.text_input("Nuova Password", type="password")
        pwd_2 = st.text_input("Conferma Password", type="password")
        
        if st.button("CONFERMA NUOVA PASSWORD"):
            if pwd_1 == pwd_2 and len(pwd_1) >= 5:
                df_dip.loc[df_dip['Nome'] == user, ['Password', 'PrimoAccesso']] = [pwd_1, False]
                df_dip.to_csv(FILE_DIPENDENTI, index=False)
                st.session_state["primo_accesso"] = False
                st.success("Password salvata con successo!")
                time.sleep(1); st.rerun()
            else:
                st.error("Errore: la password deve avere almeno 5 caratteri.")
        st.stop()

    # Calcolo Saldi in Tempo Reale
    u_info = df_dip[df_dip['Nome'] == user].iloc[0]
    usato_f = df_ferie[(df_ferie['Nome'] == user) & (df_ferie['Risorsa'] == 'Ferie')]['Valore'].sum()
    usato_r = df_ferie[(df_ferie['Nome'] == user) & (df_ferie['Risorsa'] == 'ROL')]['Valore'].sum()

    st.header(f"Area Personale: {user}")
    st.info(f"Tipo Contratto: **{u_info['Contratto']}**")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Saldo Ferie (GG)", round(u_info['Ferie'] - usato_f, 2))
    
    # Visualizzazione ROL solo per contratto FIDUCIARIO
    if u_info['Contratto'] == "Fiduciario":
        col2.metric("Saldo ROL (GG)", round(u_info['ROL'] - usato_r, 2))
        
    if col3.button("DISCONNETTI"):
        del st.session_state["user"]; st.rerun()

    # Gestione Cancellazione Richieste
    st.subheader("Le tue prenotazioni inoltrate")
    le_mie = df_ferie[df_ferie['Nome'] == user]
    
    if le_mie.empty:
        st.info("Nessun O.D.S. presente in archivio.")
    else:
        for idx_r, r_val in le_mie.iterrows():
            c_inf, c_del = st.columns([5, 1])
            c_inf.info(f"📅 **{r_val['Tipo']}** - Dal {r_val['Inizio']} al {r_val['Fine']}")
            if c_del.button("ANNULLA", key=f"btn_del_{idx_r}"):
                df_ferie = df_ferie.drop(idx_r)
                df_ferie.to_csv(FILE_FERIE, index=False)
                invia_email(f"ANNULLO: {user}", f"Cancellata {r_val['Tipo']} ({r_val['Inizio']})")
                st.rerun()

    st.divider()
    
    # Logica Visualizzazione Disponibilità (Pallini)
    def get_count(d):
        merged = df_ferie.merge(df_dip[['Nome', 'Escluso']], on='Nome')
        return len(merged[
            (pd.to_datetime(merged['Inizio']).dt.date <= d) & 
            (pd.to_datetime(merged['Fine']).dt.date >= d) & 
            (~merged['Tipo'].isin(["Permesso 104", "Congedo Parentale"])) & 
            (merged['Escluso'] == False)
        ])

    st.subheader(f"Situazione Reparto (Soglia Max: {config['limite']})")
    gg_range = pd.date_range(date.today() + timedelta(days=1), periods=10).date
    st_cols = st.columns(len(gg_range))
    
    for i_g, g_val in enumerate(gg_range):
        n_occ = get_count(g_val)
        with st_cols[i_g]:
            st.write(f"**{g_val.strftime('%d/%m')}**")
            st.write("🟢" if n_occ < config['limite'] else "🔴")
            st.caption(f"{n_occ}/{config['limite']}")

    # Modulo Inserimento O.D.S.
    with st.form("form_ods_v57"):
        st.subheader("Compila Nuova Richiesta")
        opzioni = ["Ferie", "Permesso 104", "Donazione Sangue", "Congedo Parentale"]
        if u_info['Contratto'] == "Fiduciario":
            opzioni.insert(1, "ROL")
            
        f_tipo = st.selectbox("Causale Richiesta", opzioni)
        f_dal  = st.date_input("Dalla data", min_value=date.today() + timedelta(days=1))
        f_al   = st.date_input("Alla data", min_value=date.today() + timedelta(days=1))
        
        if st.form_submit_button("INVIA O.D.S."):
            giorni_richiesti = pd.date_range(f_dal, f_al).date
            is_bloccato = False
            
            # Controllo Limiti per Guardie/Fiduciari non esclusi
            if not u_info['Escluso'] and f_tipo not in ["Permesso 104", "Congedo Parentale"]:
                if any(get_count(d) >= config['limite'] for d in giorni_richiesti):
                    is_bloccato = True
            
            if is_bloccato:
                st.error(f"Spiacente, il limite di {config['limite']} assenze è già stato raggiunto.")
            else:
                nuova_f = pd.DataFrame([[user, str(f_dal), str(f_al), f_tipo, f_tipo, len(giorni_richiesti), "GG"]], columns=df_ferie.columns)
                nuova_f.to_csv(FILE_FERIE, mode='a', header=False, index=False)
                invia_email(f"RICHIESTA: {user}", f"{f_tipo} dal {f_dal} al {f_al}")
                st.success("Richiesta inviata!"); time.sleep(1); st.rerun()
# ==============================================================================
# FOOTER DISCRETO K & L (DA INSERIRE A FINE FILE)
# ==============================================================================
st.markdown("---") # Riga di separazione sottile
st.markdown(
    """
    <div style="display: flex; justify-content: space-between; align-items: center; opacity: 0.7; padding: 10px;">
        <div style="font-size: 0.8em; color: #6c757d;">
            Battistolli HR Master v57.1 • 2026
        </div>
        <div style="text-align: right;">
            <span style="color: #ffc107; font-size: 1.2em;">★</span>
            <span style="font-family: 'Georgia', serif; font-weight: bold; color: #1c3d5a; margin-left: 5px;">K & L</span>
            <span style="font-size: 0.7em; color: #ffc107; text-transform: uppercase; display: block; letter-spacing: 1px;">Official System</span>
        </div>
    </div>
    """, 
    unsafe_allow_html=True
)
