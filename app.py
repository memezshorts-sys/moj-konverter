import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I STILIZACIJA ---
st.set_page_config(page_title="Panda Konverter", page_icon="🐼", layout="wide")

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

st.title("🐼 Panda Multi-Bank (HPB & RBA)")

# --- 2. FUNKCIJA ZA EKSTRAKCIJU ---
def extract_transactions(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        raw_text = ""
        for page in pdf.pages:
            raw_text += page.extract_text() + "\n"
    
    # SKRAĆENA LINIJA (da izbjegnemo SyntaxError)
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    
    is_hpb = "HRVATSKA POSTANSKA BANKA" in raw_text.upper()
    
    iban_pat = re.compile(r'HR\d{19}')
    date_pat = re.compile(r'(\d{2}\.\d{2}\.\d{4})')
    amt_pat = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})$')

    results = []
    
    for i, line in enumerate(lines):
        clean_l = line.replace(" ", "")
        if iban_pat.search(clean_l):
            iban = iban_pat.search(clean_l).group(0)
            datum, duguje, naziv = "-", 0.0, line.split(iban)[-1].strip()
            
            if len(naziv) < 3 and i > 0:
                naziv = lines[i-1]

            # HPB/RBA blok pretraživanje
            for off in range(i, i + 6):
                if 0 <= off < len(lines):
                    s_line = lines[off]
                    dates = date_pat.findall(s_line)
                    if dates: datum = dates[-1]
                    
                    match_amt = amt_pat.search(s_line)
                    if match_amt:
                        duguje = float(match_amt.group(1).replace('.','').replace(',','.'))

            if duguje > 0:
                results.append({
                    "Datum": datum,
                    "Konto": "2221",
                    "Naziv": naziv[:35],
                    "IBAN": iban,
                    "Duguje": "{:.2f}".format(duguje),
                    "Potražuje": "0.00"
                })

    return results, "HPB" if is_hpb else "RBA/Ostalo"

# --- 3. WEB SUČELJE ---
up_file = st.file_uploader("Prenesite PDF izvadak", type="pdf")

if up_file:
    try:
        data, bank = extract_transactions(up_file)
        if data:
            st.success(f"Banka: **{bank}**")
            suma = sum(float(t["Duguje"]) for t in data)
            
            # Konto 1000 za kraj
            data.append({
                "Datum": data[-1]["Datum"],
                "Konto": "1000",
                "Naziv": "UKUPAN IZVOD",
                "IBAN": "",
                "Duguje": "0.00",
                "Potražuje": "{:.2f}".format(suma)
            })
            
            st.table(data)
            st.info(f"Ukupno: {suma:.2f} EUR")
        else:
            st.warning("Nema podataka.")
    except Exception as e:
        st.error(f"Greška: {e}")
