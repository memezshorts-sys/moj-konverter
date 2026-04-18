import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. Postavke stranice - MORA BITI PRVO
st.set_page_config(page_title="Panda Multi-Bank", page_icon="🐼", layout="centered")

# --- DIZAJN I STILIZACIJA (Zadržane sve tvoje postavke) ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    
    /* Gumb za sidebar fix */
    button[kind="headerNoPadding"] {
        background-color: #00d2ff !important;
        color: black !important;
        border-radius: 50% !important;
        z-index: 999999 !important;
    }

    .stApp::before {
        content: 'PANDA KNJIGOVODSTVO';
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%) rotate(-30deg);
        font-size: 8vw; font-weight: 900;
        color: rgba(255, 255, 255, 0.04);
        white-space: nowrap; pointer-events: none; z-index: 0;
        letter-spacing: 15px; text-transform: uppercase;
    }

    [data-testid="stSidebar"] { background-color: #161625 !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h1 {
        color: #ffffff !important;
        font-weight: bold !important;
    }

    div[data-baseweb="select"] > div {
        background-color: #2d3436 !important;
        color: white !important;
        border: 1px solid #00d2ff !important;
    }

    ul[role="listbox"] { background-color: #2d3436 !important; }
    li[role="option"] { background-color: #2d3436 !important; color: white !important; }
    li[role="option"]:hover { background-color: #00d2ff !important; color: black !important; }

    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    
    [data-testid="stFileUploader"] { 
        background-color: #d1d1d1 !important; 
        border-radius: 15px !important; 
        padding: 30px !important; 
    }
    [data-testid="stFileUploader"] section div { color: #1e1e2f !important; }
    
    .stDownloadButton button { 
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important; 
        color: white !important; 
        border-radius: 50px !important; 
        width: 100%; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- IZBORNIK ---
st.sidebar.title("🐼 Panda Postavke")
banka = st.sidebar.selectbox("Odaberite banku:", ("Univerzalni Konverter", "HPB", "RBA"))

st.title(f"📄 {banka} Konverter")

# --- LOGIKA ISČITAVANJA (VRAĆENA STARA DETALJNA LOGIKA) ---
def extract_all_data(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    iban_pattern = re.compile(r'HR\d{19}')
    amount_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')
    date_pattern = re.compile(r'(\d{2}\.\d{2}\.\d{4})')

    detected_transactions = []
    
    for i, line in enumerate(lines):
        clean_line = line.replace(" ", "")
        iban_match = iban_pattern.search(clean_line)
        
        if iban_match:
            iban = iban_match.group(0)
            amount = 0.0
            naziv = "Nepoznati Partner"
            datum = "-"
            
            # Detaljno skeniranje okoline za Datum, Iznos i Naziv
            search_range = range(-3, 5) if banka != "Univerzalni Konverter" else range(-2, 4)
            for offset in search_range:
                if 0 <= i + offset < len(lines):
                    search_line = lines[i+offset]
                    
                    # 1. Traženje iznosa
                    am_matches = amount_pattern.findall(search_line)
                    for am in am_matches:
                        val = float(am.replace('.', '').replace(',', '.'))
                        if val > 1.0 and amount == 0.0:
                            amount = val
                    
                    # 2. Traženje datuma
                    d_match = date_pattern.search(search_line)
                    if d_match and datum == "-":
                        datum = d_match.group(1)
                    
                    # 3. Traženje naziva
                    if naziv == "Nepoznati Partner" and len(search_line) > 3:
                        if not any(char.isdigit() for char in search_line) and "HR" not in search_line:
                            naziv = search_line

            if amount > 0:
                detected_transactions.append({
                    "Datum": datum,
                    "Konto": "2221",
                    "Naziv": naziv[:35],
                    "IBAN": iban,
                    "Duguje": "{:.2f}".format(amount).replace('.', ','),
                    "Potražuje": "0,00"
                })
    
    return detected_transactions, text

def generate_hub3(transactions):
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    ET.register_namespace('', ns)
    root = ET.Element("{%s}Document" % ns)
    initn = ET.SubElement(root, "{%s}CstmrCdtTrfInitn" % ns)
    grphdr = ET.SubElement(initn, "{%s}GrpHdr" % ns)
    ET.SubElement(grphdr, "{%s}MsgId" % ns).text = f"ID-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "{%s}CreDtTm" % ns).text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "{%s}NbOfTxs" % ns).text = str(len(transactions))
    pmt_inf = ET.SubElement(initn, "{%s}PmtInf" % ns)
    ET.SubElement(pmt_inf, "{%s}PmtInfId" % ns).text = "ISPLATA-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, "{%s}PmtMtd" % ns).text = "TRF"
    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, "{%s}CdtTrfTxInf" % ns)
        p_id = ET.SubElement(tx_inf, "{%s}PmtId" % ns)
        ET.SubElement(p_id, "{%s}EndToEndId" % ns).text = "HR99"
        amt = ET.SubElement(tx_inf, "{%s}Amt" % ns)
        val = tx['Duguje'].replace(',', '.')
        ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = val
        cdtr = ET.SubElement(tx_inf, "{%s}Cdtr" % ns)
        ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv']
        rmt = ET.SubElement(tx_inf, "{%s}RmtInf" % ns)
        ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"
    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# --- UI ---
uploaded_file = st.file_uploader("Povucite PDF izvadak ovdje", type="pdf")

if uploaded_file:
    try:
        data, raw_text = extract_all_data(uploaded_file)
        if data:
            # Izračun i dodavanje Konta 1000 (Izvod)
            suma = sum(float(tx["Duguje"].replace(',', '.')) for tx in data)
            current_date = data[0]["Datum"] if data[0]["Datum"] != "-" else datetime.now().strftime('%d.%m.%Y')

            # Provjera naknade (samo ako postoji)
            if "0,40" in raw_text:
                data.append({"Datum": current_date, "Konto": "4650", "Naziv": "Naknada banke", "IBAN": "", "Duguje": "0,40", "Potražuje": "0,00"})
                suma += 0.40
            
            data.append({"Datum": current_date, "Konto": "1000", "Naziv": "Izvod", "IBAN": "", "Duguje": "0,00", "Potražuje": "{:.2f}".format(suma).replace('.', ',')})
            
            st.table(data)
            hub3_res = generate_hub3([t for t in data if t["Konto"] != "1000"])
            st.download_button("⬇️ Preuzmi HUB3", hub3_res, f"izvod_{banka.lower()}.hub3")
        else:
            st.warning("Nije pronađeno ništa u PDF-u.")
    except Exception as e:
        st.error(f"Greška: {e}")
