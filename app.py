import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I KONFIGURACIJA ---
st.set_page_config(page_title="Panda Multi-Bank", page_icon="🐼", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    [data-testid="stSidebar"] { background-color: #1e1e2f !important; border-right: 1px solid #00d2ff; }
    [data-testid="stFileUploader"] { background-color: #d1d1d1 !important; border-radius: 15px !important; padding: 20px !important; }
    [data-testid="stFileUploader"] section div p { color: #000000 !important; font-weight: bold !important; }
    [data-testid="stFileUploader"] button { background-color: #000000 !important; color: #ffffff !important; }
    .stTable { background-color: rgba(255, 255, 255, 0.05); border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIKA ZA SPECIFIČNE BANKE ---

def parse_hpb(text):
    results = []
    lines =
    iban_pattern = re.compile(r'HR\d{19}')
    amount_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')
    date_pattern = re.compile(r'(\d{2}\.\d{2}\.\d{4})')

    for i, line in enumerate(lines):
        clean_line = line.replace(" ", "")
        if iban_match := iban_pattern.search(clean_line):
            iban = iban_match.group(0)
            # HPB: Naziv je obično u istom redu nakon IBAN-a ili odmah ispod
            naziv = line.split(iban)[-1].strip() if iban in line else "Nepoznat"
            if not naziv or len(naziv) < 3:
                if i + 1 < len(lines): naziv = lines[i+1]
            
            amount = 0.0
            datum = ""
            # Traži u iduća 4 reda
            for offset in range(1, 5):
                if i + offset < len(lines):
                    s_line = lines[i+offset]
                    if not datum:
                        if d_m := date_pattern.search(s_line): datum = d_m.group(0)
                    if am_matches := amount_pattern.findall(s_line):
                        # HPB stavlja duguje/potražuje u tablicu, uzimamo prvu cifru kao isplatu
                        amount = float(am_matches[0].replace('.', '').replace(',', '.'))
            
            results.append({"Datum": datum, "Konto": "2221", "Naziv": naziv[:35], "IBAN": iban, "Duguje": "{:.2f}".format(amount), "Potražuje": "0.00"})
    return results

def parse_rba(text):
    results = []
    lines =
    iban_pattern = re.compile(r'HR\d{19}')
    amount_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')
    
    for i, line in enumerate(lines):
        if iban_match := iban_pattern.search(line.replace(" ", "")):
            iban = iban_match.group(0)
            # RBA: Naziv je često red iznad ili dva reda ispod IBAN-a
            naziv = "Partner"
            if i - 1 >= 0: naziv = lines[i-1]
            
            amount = 0.0
            datum = ""
            for offset in range(-2, 4):
                if 0 <= i + offset < len(lines):
                    s_line = lines[i+offset]
                    if am_matches := amount_pattern.findall(s_line):
                        val = float(am_matches[0].replace('.', '').replace(',', '.'))
                        if val > 1.0: amount = val
                    if re.search(r'\d{2}\.\d{2}\.\d{4}', s_line):
                        datum = re.search(r'\d{2}\.\d{2}\.\d{4}', s_line).group(0)

            results.append({"Datum": datum, "Konto": "2221", "Naziv": naziv[:35], "IBAN": iban, "Duguje": "{:.2f}".format(amount), "Potražuje": "0.00"})
    return results

# --- 3. UI I PROCESIRANJE ---

with st.sidebar:
    st.title("🐼 Panda Postavke")
    banka = st.selectbox("Odaberite banku za preciznije čitanje:", ["HPB", "RBA", "Univerzalno"])
    st.info(f"Trenutni algoritam prilagođen za: {banka}")

st.title("📄 Profesionalni PDF Konverter")

uploaded_file = st.file_uploader("Povucite izvadak (PDF)", type="pdf")

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        raw_text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])

    if banka == "HPB":
        data = parse_hpb(raw_text)
    elif banka == "RBA":
        data = parse_rba(raw_text)
    else:
        # Univerzalna logika (tvoj originalni kod)
        data = parse_hpb(raw_text) # Default na HPB stil jer je robusniji

    if data:
        # Kalkulacija naknade i ukupnog (Konto 1000)
        ukupno = sum(float(tx["Duguje"]) for tx in data)
        datum_izvoda = data[0]["Datum"] if data else datetime.now().strftime('%d.%m.%Y')
        
        # Dodavanje naknade ako je nađena u tekstu (specifično za HR banke)
        if "0,40" in raw_text:
            data.append({"Datum": datum_izvoda, "Konto": "4650", "Naziv": "Bankovna naknada", "IBAN": "", "Duguje": "0.40", "Potražuje": "0.00"})
            ukupno += 0.40
            
        data.append({"Datum": datum_izvoda, "Konto": "1000", "Naziv": "UKUPNO IZVOD", "IBAN": "", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno)})
        
        st.subheader(f"Rezultati analize ({banka})")
        st.table(data)
        
        # Ovdje bi išao tvoj generate_hub3 poziv...
        st.success("Podaci su spremni za izvoz u HUB3.")
    else:
        st.error("Nije moguće očitati podatke. Provjerite je li PDF tekstualni (ne skeniran).")
