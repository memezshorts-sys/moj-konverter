import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I STILIZACIJA ---
st.set_page_config(page_title="Panda Multi-Bank Konverter", page_icon="🐼", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    .stApp::before {
        content: 'PANDA KNJIGOVODSTVO';
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%) rotate(-30deg);
        font-size: 8vw; font-weight: 900;
        color: rgba(255, 255, 255, 0.04);
        white-space: nowrap; pointer-events: none; z-index: 0;
        letter-spacing: 15px; text-transform: uppercase;
    }
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    [data-testid="stFileUploader"] {
        background-color: #d1d1d1 !important;
        border: 2px solid #a0a0a0 !important;
        border-radius: 15px !important;
        padding: 30px !important;
    }
    [data-testid="stFileUploader"] section div { color: #1e1e2f !important; }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important;
        color: white !important;
        border-radius: 50px !important;
        font-weight: bold !important;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🐼 Panda Multi-Bank (RBA & HPB)")

# --- 2. FUNKCIJA ZA EKSTRAKCIJU PODATAKA ---
def extract_transactions(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    
    # LINIJA 43 - SADA ISPRAVLJENA
    lines =
    
    is_hpb = "HRVATSKA POSTANSKA BANKA" in text.upper()
    
    iban_pattern = re.compile(r'HR\d{19}')
    date_pattern = re.compile(r'(\d{2}\.\d{2}\.\d{4})')
    # Hvata iznos na kraju linije (format za HPB i RBA)
    amount_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})$')

    detected_transactions = []
    
    for i, line in enumerate(lines):
        clean_line = line.replace(" ", "")
        iban_match = iban_pattern.search(clean_line)
        
        if iban_match:
            iban = iban_match.group(0)
            datum = "-"
            # Uzimamo naziv koji je obično desno od IBAN-a ili u redu iznad
            naziv = line.split(iban)[-1].strip() or "Nepoznati Partner"
            if len(naziv) < 3 and i > 0: naziv = lines[i-1] # Fix za HPB naslove

            duguje = 0.0
            potrazuje = 0.0

            # Pretraživanje blokova (HPB ima podatke u 4-5 redova ispod IBAN-a)
            search_range = range(i, i + 6)
            for offset in search_range:
                if 0 <= offset < len(lines):
                    s_line = lines[offset]
                    
                    # 1. Datum (uzimamo zadnji pronađeni datum u bloku - Datum izvršenja)
                    dates = date_pattern.findall(s_line)
                    if dates:
                        datum = dates[-1]

                    # 2. Iznos (HPB/RBA kolone)
                    am_match = amount_pattern.search(s_line)
                    if am_match:
                        val = float(am_match.group(1).replace('.', '').replace(',', '.'))
                        # Ako je HPB, iznosi na desnoj strani su obično isplate (Duguje)
                        # Ovdje možeš dodati logiku za Potražuje ako tvoj PDF ima tu kolonu popunjenu
                        duguje = val

            if duguje > 0 or potrazuje > 0:
                detected_transactions.append({
                    "Datum": datum,
                    "Konto": "2221",
                    "Naziv": naziv[:35],
                    "IBAN": iban,
                    "Duguje": "{:.2f}".format(duguje),
                    "Potražuje": "{:.2f}".format(potrazuje)
                })

    return detected_transactions, "HPB" if is_hpb else "RBA/Ostalo"

# --- 3. WEB SUČELJE ---
uploaded_file = st.file_uploader("Prenesite PDF izvadak", type="pdf")

if uploaded_file:
    try:
        data, bank_name = extract_transactions(uploaded_file)
        
        if data:
            st.success(f"Prepoznat format: **{bank_name}**")
            
            # Izračun ukupnog prometa
            suma_duguje = sum(float(t["Duguje"]) for t in data)
            suma_potrazuje = sum(float(t["Potražuje"]) for t in data)
            
            # Dodavanje finalne stavke za Konto 1000 (Izvod)
            zadnji_datum = data[-1]["Datum"]
            data.append({
                "Datum": zadnji_datum,
                "Konto": "1000",
                "Naziv": "UKUPNO PO IZVODU",
                "IBAN": "",
                "Duguje": "{:.2f}".format(suma_potrazuje),
                "Potražuje": "{:.2f}".format(suma_duguje)
            })
            
            st.table(data)
            st.info(f"🚀 Ukupan iznos za knjiženje: **{suma_duguje:.2f} EUR**")
            
            # Ovdje možeš pozvati svoju funkciju za generiranje XML-a
            # hub3_data = generate_hub3(data)
            
        else:
            st.warning("Nema pronađenih podataka. Provjerite PDF.")
            
    except Exception as e:
        st.error(f"Došlo je do greške: {e}")
