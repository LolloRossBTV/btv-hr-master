import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- INIZIALIZZAZIONE ---
if 'autenticato' not in st.session_state:
    st.session_state.autenticato = False

# --- CARICAMENTO DATI (Blindato contro l'errore rosa) ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_dip = conn.read(worksheet="Dipendenti", ttl=0)
    
    # Pulizia sicura dei nomi: trasformiamo la colonna in stringhe PRIMA del match
    # Questo risolve l'errore 'Series' degli screenshot
    df_dip['Nome_Clean'] = df_dip['Nome'].astype(str).str.strip().str.upper()
except Exception as e:
    st.error(f"Errore nel database: {e}")
    st.stop()

# --- LOGIN ---
if not st.session_state.autenticato:
    st.title("🛡️ Accesso BTV")
    # Nota per Lorenzo: Scrivi COGNOME poi NOME (es: ROSSINI LORENZO)
    u_in = st.text_input("Inserisci Cognome e Nome").strip().upper()
    p_in = st.text_input("Password", type="password")
    
    if st.button("Accedi"):
        # Controlliamo se il nome inserito esiste nella colonna pulita
        if u_in in df_dip['Nome_Clean'].values:
            idx = df_dip[df_dip['Nome_Clean'] == u_in].index[0]
            # Pulizia password (evita l'errore del .0 sui numeri)
            pw_db = str(df_dip.iloc[idx]['Password']).split('.')[0].strip()
            
            if str(p_in).strip() == pw_db:
                st.session_state.utente_loggato = df_dip.iloc[idx]['Nome']
                st.session_state.autenticato = True
                st.rerun()
            else:
                st.error("❌ Password errata")
        else:
            st.error("❌ Utente non trovato. Controlla l'ordine (Cognome Nome)")

else:
    # --- AREA PRIVATA ---
    st.sidebar.write(f"👤 {st.session_state.utente_loggato}")
    if st.sidebar.button("Logout"):
        st.session_state.autenticato = False
        st.rerun()
    
    st.header("I tuoi Saldi")
    user_data = df_dip[df_dip['Nome'] == st.session_state.utente_loggato]
    st.table(user_data[['Ferie', 'ROL', 'Contratto']])
    
    # Area Admin (Solo per te)
    if "ROSSINI" in st.session_state.utente_loggato.upper():
        st.divider()
        st.subheader("⚙️ Area Amministratore")
        st.dataframe(df_dip.drop(columns=['Nome_Clean']))
