import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I STILIZACIJA (Panda stil) ---
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
    </style>
    """, unsafe_allow_html=True)

st.title("🐼 Panda Multi-Bank (RBA & HPB)")

# --- 2. LOGIKA ZA EKSTRAKCIJU PODATAKA ---
def extract_transactions(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    
    lines =
    
    # Detekcija banke
    is_hpb = "HRVATSKA POSTANSKA BANKA" in text.upper()
    is_rba = "RAIFFEISEN" in text.upper() or "RBA" in text.upper()
    
    iban_pattern = re.compile(r'HR\d{19}')
    date_pattern = re.compile(r'(\d{2}\.\d{2}\.\d{4})')
    # Hvata iznos na kraju linije (format 1.234,56 ili 123,45)
    amount_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})$')

    transactions = []
    
    for i, line in enumerate(lines):
        clean_line = line.replace(" ", "")
        iban_match = iban_pattern.search(clean_line)
        
        if iban_match:
            iban = iban_match.group(0)
            datum = "-"
            naziv = line.split(iban)[-1].strip() or "Nepoznati Partner"
            duguje = 0.0
            potrazuje = 0.0

            # --- SPECIFIČNO PRETRAŽIVANJE ZA HPB I RBA ---
            # Gledamo linije oko IBAN-a (obično 4 linije ispod)
            search_range = range(i - 1, i + 5) if is_hpb else range(i, i + 2)
            
            for offset in search_range:
                if 0 <= offset < len(lines):
                    s_line = lines[offset]
                    
                    # 1. Isčitavanje datuma
                    dates = date_pattern.findall(s_line)
                    if dates and datum == "-":
                        # HPB: Datum izvršenja je obično zadnji u bloku
                        datum = dates[-1] if is_hpb else dates[0]

                    # 2. Isčitavanje iznosa (Duguje/Potražuje)
                    am_match = amount_pattern.search(s_line)
                    if am_match:
                        val_str = am_match.group(1).replace('.', '').replace(',', '.')
                        val = float(val_str)
                        
                        # Logika za kolone (HPB specifično)
                        if is_hpb:
                            # Ako linija sadrži "Duguje" ili je u gornjem dijelu bloka
                            duguje = val 
                        else:
                            # Za RBA i ostale
                            duguje = val

            if duguje > 0 or potrazuje > 0:
                transactions.append({
                    "Datum": datum,
                    "Konto": "2221",
                    "Naziv": naziv[:35],
                    "IBAN": iban,
                    "Duguje": "{:.2f}".format(duguje),
                    "Potražuje": "{:.2f}".format(potrazuje)
                })

    return transactions, "HPB" if is_hpb else ("RBA" if is_rba else "Univerzalni")

# --- 3. WEB SUČELJE ---
uploaded_file = st.file_uploader("Prenesite PDF izvadak (RBA ili HPB)", type="pdf")

if uploaded_file:
    try:
        data, bank_type = extract_transactions(uploaded_file)
        
        if data:
            st.success(f"Bankovni format prepoznat: **{bank_type}**")
            
            ukupno_duguje = sum(float(t["Duguje"]) for t in data)
            ukupno_potrazuje = sum(float(t["Potražuje"]) for t in data)
            
            # Dodavanje finalnog konta 1000 (Izvod)
            zadnji_datum = data[-1]["Datum"] if data else datetime.now().strftime('%d.%m.%Y')
            data.append({
                "Datum": zadnji_datum,
                "Konto": "1000",
                "Naziv": "UKUPNO PO IZVODU",
                "IBAN": "",
                "Duguje": "{:.2f}".format(ukupno_potrazuje),
                "Potražuje": "{:.2f}".format(ukupno_duguje)
            })

            st.table(data)
            
            # TODO: Ovdje ide tvoja generate_hub3 funkcija
            st.info("Podaci su spremni za HUB3 generiranje.")
            
        else:
            st.warning("Nisu pronađene transakcije. Provjerite format PDF-a.")
            
    except Exception as e:
        st.error(f"Greška prilikom čitanja: {e}")
