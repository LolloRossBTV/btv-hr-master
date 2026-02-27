import streamlit as st
import pandas as pd
import os
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
import time
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# 1. CONFIGURAZIONE E CONNESSIONE GOOGLE SHEETS
# ==============================================================================
st.set_page_config(page_title="Battistolli HR Master v57.1", layout="wide")

# Connessione al foglio Google tramite st.secrets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Proviamo subito a leggere per vedere se esplode qui
    test_df = conn.read(worksheet="Dipendenti", ttl="0s")
except Exception as e:
    st.error("⚠️ ERRORE DI CONNESSIONE RILEVATO:")
    st.code(str(e))
    st.stop()

def carica_dati_google():
    """Legge i dati direttamente dal foglio Google Online"""
    try:
        # ttl="0s" assicura che l'app legga sempre l'ultima modifica sul foglio
        df = conn.read(ttl="0s")
        return df
    except Exception as e:
        st.error(f"Errore di connessione a Google Sheets: {e}")
        return None

def salva_dati_google(df):
    """Scrive i dati aggiornati direttamente sul foglio Google"""
    try:
        conn.update(data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Errore durante il salvataggio: {e}")
        return False

# Credenziali amministrative
PASSWORD_ADMIN  = "admin2024"

# ------------------------------------------------------------------------------
# PARAMETRI DI MATURAZIONE MENSILE (Specifiche Contrattuali 2026)
# ------------------------------------------------------------------------------
MAT_FERIE_GUARDIA    = 1.917
MAT_FERIE_FIDUCIARIO = 2.16 
MAT_ROL_FIDUCIARIO   = 0.60 

# ==============================================================================
# 2. FUNZIONI DI SISTEMA (NOTIFICHE E CONFIGURAZIONE)
# ==============================================================================
def invia_email(oggetto, corpo):
    """Gestisce l'invio delle notifiche via email utilizzando i Secrets corretti."""
    try:
        if "emails" not in st.secrets:
            return False
            
        msg = MIMEText(corpo)
        msg['Subject'] = oggetto
        msg['From'] = st.secrets["emails"]["sender_email"]
        msg['To'] = st.secrets["emails"].get("receiver_email", st.secrets["emails"]["sender_email"])
        
        with smtplib.SMTP(st.secrets["emails"]["smtp_server"], st.secrets["emails"]["smtp_port"]) as server:
            server.starttls()
            server.login(st.secrets["emails"]["sender_email"], st.secrets["emails"]["sender_password"])
            server.sendmail(st.secrets["emails"]["sender_email"], [msg['To']], msg.as_string())
        return True
    except:
        return False

FILE_FERIE = 'db_ferie.csv'
FILE_CONFIG = 'db_config.csv'

def carica_config():
    if not os.path.exists(FILE_CONFIG):
        mese_scorso = (datetime.now().month - 1) if datetime.now().month > 1 else 12
        pd.DataFrame([{"limite": 3, "ultimo_mese": mese_scorso}]).to_csv(FILE_CONFIG, index=False)
    config_df = pd.read_csv(FILE_CONFIG)
    return config_df.iloc[0]

def salva_config(nuovo_limite, nuovo_mese):
    pd.DataFrame([{"limite": nuovo_limite, "ultimo_mese": nuovo_mese}]).to_csv(FILE_CONFIG, index=False)

# ==============================================================================
# 3. LOGICA DI CALCOLO MATURAZIONE (GUARDIE vs FIDUCIARI)
# ==============================================================================
def applica_maturazione(df_dip):
    for idx, row in df_dip.iterrows():
        if row['Contratto'] == "Guardia":
            df_dip.at[idx, 'Ferie'] += MAT_FERIE_GUARDIA
        else:
            df_dip.at[idx, 'Ferie'] += MAT_FERIE_FIDUCIARIO
            df_dip.at[idx, 'ROL'] += MAT_ROL_FIDUCIARIO
    return df_dip

def aggiorna_maturazioni_mensili(df_dip, config):
    oggi = datetime.now()
    try:
        ultimo_registrato = int(config['ultimo_mese'])
    except:
        ultimo_registrato = oggi.month

    if oggi.month != ultimo_registrato:
        st.info(f"🔄 Cambio mese rilevato. Aggiornamento saldi...")
        df_dip = applica_maturazione(df_dip)
        salva_dati_google(df_dip) # Sincronizza subito su Google
        salva_config(config['limite'], oggi.month)
        st.success("Maturazione mensile completata!")
        time.sleep(1)
        st.rerun()
    return df_dip

# ==============================================================================
# 4. INIZIALIZZAZIONE DATABASE
# ==============================================================================
# Carichiamo i dati da Google Sheets invece che dal CSV locale
df_dip = carica_dati_google()

if not os.path.exists(FILE_FERIE):
    pd.DataFrame(columns=['Nome','Inizio','Fine','Tipo','Risorsa','Valore','Unita']).to_csv(FILE_FERIE, index=False)
df_ferie = pd.read_csv(FILE_FERIE)

config = carica_config()
if df_dip is not None:
    df_dip = aggiorna_maturazioni_mensili(df_dip, config)

# CSS Personalizzato
st.markdown("""
    <style>
    .metric-container { background-color: #f1f3f5; border: 1px solid #ced4da; padding: 20px; border-radius: 12px; }
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
            if u_in == "ADMIN" and p_in == PASSWORD_ADMIN:
                st.session_state["user"] = "admin"
                st.rerun()
            
            if df_dip is not None:
                # Logica di confronto nomi originale
                input_set = set(u_in.split())
                for idx, row in df_dip.iterrows():
                    db_name_set = set(str(row['Nome']).upper().split())
                    if input_set == db_name_set and str(row['Password']) == p_in:
                        st.session_state["user"] = row['Nome']
                        st.session_state["primo_accesso"] = row.get('PrimoAccesso', False)
                        st.rerun()
            
            st.error("Dati non validi. Controlla il Foglio Google.")
    st.stop()

user = st.session_state["user"]

# ==============================================================================
# 5. AREA AMMINISTRATORE (HR & GESTIONE ORGANICO)
# ==============================================================================
if user == "admin":
    st.header("👨‍💼 Pannello di Gestione HR")
    tabs = st.tabs(["Registro Richieste", "Gestione Personale", "Configurazione Sistema"])
    
    with tabs[0]:
        st.subheader("Tutte le richieste inoltrate")
        st.dataframe(df_ferie, use_container_width=True)
        if st.button("Logout Amministratore"):
            del st.session_state["user"]; st.rerun()
            
    with tabs[1]:
        col_main, col_side = st.columns([2, 1])
        with col_main:
            st.subheader("1. Modifica Dati su Google Sheets")
            # Qui modifichi i dati che poi finiscono su Google
            df_editor = st.data_editor(df_dip, use_container_width=True, num_rows="dynamic", key="admin_editor")
            if st.button("💾 SALVA MODIFICHE SU GOOGLE SHEETS"):
                if salva_dati_google(df_editor):
                    st.success("Foglio Google aggiornato!")
                    time.sleep(0.5); st.rerun()

        with col_side:
            st.subheader("2. Operazioni Organico")
            with st.expander("🆕 Nuova Assunzione"):
                new_n = st.text_input("Cognome Nome").upper().strip()
                new_t = st.selectbox("Contratto", ["Fiduciario", "Guardia"])
                if st.button("AGGIUNGI"):
                    # Logica aggiunta record
                    new_row = pd.DataFrame([[new_n, 0.0, 0.0, new_t, "12345", True, "Attivo"]], columns=df_dip.columns)
                    df_dip = pd.concat([df_dip, new_row], ignore_index=True)
                    salva_dati_google(df_dip)
                    st.success("Aggiunto!"); st.rerun()

    with tabs[2]:
        st.subheader("Parametri Operativi")
        nuova_soglia = st.slider("Limite assenze", 1, 15, int(config['limite']))
        if st.button("Salva Soglia"):
            salva_config(nuova_soglia, config['ultimo_mese'])
            st.success("Limite aggiornato!")

# ==============================================================================
# 6. AREA UTENTE (GUARDIE E FIDUCIARI)
# ==============================================================================
else:
    u_info = df_dip[df_dip['Nome'] == user].iloc[0]
    usato_f = df_ferie[(df_ferie['Nome'] == user) & (df_ferie['Risorsa'] == 'Ferie')]['Valore'].sum()
    usato_r = df_ferie[(df_ferie['Nome'] == user) & (df_ferie['Risorsa'] == 'ROL')]['Valore'].sum()

    st.header(f"Area Personale: {user}")
    st.info(f"Contratto: **{u_info['Contratto']}**")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ferie (GG)", round(u_info['Ferie'] - usato_f, 2))
    if u_info['Contratto'] == "Fiduciario":
        col2.metric("ROL (GG)", round(u_info['ROL'] - usato_r, 2))
    if col3.button("LOGOUT"):
        del st.session_state["user"]; st.rerun()

    st.divider()
    
    def get_count(d):
        merged = df_ferie.merge(df_dip[['Nome', 'Escluso']], on='Nome')
        return len(merged[(pd.to_datetime(merged['Inizio']).dt.date <= d) & 
                          (pd.to_datetime(merged['Fine']).dt.date >= d) & 
                          (~merged['Tipo'].isin(["Permesso 104"])) & (merged['Escluso'] == False)])

    st.subheader(f"Situazione Reparto (Soglia: {config['limite']})")
    gg_range = pd.date_range(date.today() + timedelta(days=1), periods=10).date
    st_cols = st.columns(len(gg_range))
    
    for i_g, g_val in enumerate(gg_range):
        n_occ = get_count(g_val)
        with st_cols[i_g]:
            st.write(f"**{g_val.strftime('%d/%m')}**")
            st.write("🟢" if n_occ < config['limite'] else "🔴")
            st.caption(f"{n_occ}/{config['limite']}")

    with st.form("form_ods"):
        st.subheader("Nuova Richiesta O.D.S.")
        opzioni = ["Ferie", "Permesso 104", "Donazione Sangue"]
        if u_info['Contratto'] == "Fiduciario": opzioni.insert(1, "ROL")
        f_tipo = st.selectbox("Causale", opzioni)
        f_dal = st.date_input("Dalla data")
        f_al = st.date_input("Alla data")
        
        if st.form_submit_button("INVIA"):
            giorni = pd.date_range(f_dal, f_al).date
            if not u_info['Escluso'] and f_tipo not in ["Permesso 104"] and any(get_count(d) >= config['limite'] for d in giorni):
                st.error("Posti esauriti per le date scelte.")
            else:
                nuova_f = pd.DataFrame([[user, str(f_dal), str(f_al), f_tipo, f_tipo, len(giorni), "GG"]], columns=df_ferie.columns)
                nuova_f.to_csv(FILE_FERIE, mode='a', header=False, index=False)
                invia_email(f"RICHIESTA: {user}", f"{f_tipo} dal {f_dal} al {f_al}")
                st.success("Richiesta inviata correttamente!"); time.sleep(1); st.rerun()

st.markdown("---")
st.markdown("<div style='text-align: right; opacity: 0.7;'>K & L Official System • 2026</div>", unsafe_allow_html=True)
