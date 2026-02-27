import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAZIONE ---
MAT_FERIE_GUARDIA = 1.83
MAT_FERIE_FIDUCIARIO = 1.50
MAT_ROL_FIDUCIARIO = 0.50

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["emails"]["sender_email"]
        msg['To'] = st.secrets["emails"]["receiver_email"]
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(st.secrets["emails"]["smtp_server"], st.secrets["emails"]["smtp_port"])
        server.starttls()
        server.login(st.secrets["emails"]["sender_email"], st.secrets["emails"]["sender_password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Errore invio email: {e}")
        return False

def applica_maturazione(df_dip):
    df_dip['Ferie'] = pd.to_numeric(df_dip['Ferie'], errors='coerce').fillna(0)
    df_dip['ROL'] = pd.to_numeric(df_dip['ROL'], errors='coerce').fillna(0)
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
        last_upd_str = config.get('last_update', '2000-01-01')
        ultimo_aggiornamento = pd.to_datetime(last_upd_str)
        if oggi.month != ultimo_aggiornamento.month or oggi.year != ultimo_aggiornamento.year:
            st.info("🔄 Cambio mese rilevato. Aggiornamento saldi...")
            df_dip = applica_maturazione(df_dip)
            config['last_update'] = oggi.strftime('%Y-%m-%d')
            return df_dip, True
    except Exception as e:
        return df_dip, False
    return df_dip, False

# --- CONNESSIONE DATI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    df_richieste = conn.read(worksheet="Richieste", ttl=0)
    config_df = conn.read(worksheet="Config", ttl=0)
    config = dict(zip(config_df.key, config_df.value))
    df_dip, aggiornato = aggiorna_maturazioni_mensili(df_dip, config)
except Exception as e:
    st.error(f"⚠️ Errore di connessione: {e}")
    st.stop()

# --- INTERFACCIA ---
st.title("Sistema Gestione Ferie BTV")
menu = ["Visualizza Saldi", "Inserisci Richiesta", "Gestione Admin"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Visualizza Saldi":
    st.subheader("Saldi Ferie e ROL")
    st.dataframe(df_dip)

elif choice == "Inserisci Richiesta":
    st.subheader("Nuova Richiesta")
    with st.form("form_richiesta"):
        nome = st.selectbox("Dipendente", df_dip['Nome'].tolist())
        tipo = st.radio("Tipo", ["Ferie", "ROL", "Permesso"])
        inizio = st.date_input("Dal")
        fine = st.date_input("Al")
        note = st.text_area("Note")
        submit = st.form_submit_button("Invia Richiesta")
        
        if submit:
            messaggio = f"Nuova richiesta da {nome}: {tipo} dal {inizio} al {fine}\nNote: {note}"
            if send_email(f"Richiesta {tipo} - {nome}", messaggio):
                st.success("Richiesta inviata via e-mail con successo!")
            else:
                st.warning("Richiesta registrata ma errore nell'invio e-mail.")

elif choice == "Gestione Admin":
    st.subheader("Area Riservata Amministrazione")
    st.write("Richieste Ricevute:")
    st.dataframe(df_richieste)
