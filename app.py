import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. MORA BITI PRVO - SAMO JEDNOM U CIJELOM KODU
st.set_page_config(page_title="Panda Univerzalni Konverter", page_icon="🐼", layout="centered")

# --- ZAJEDNIČKI DIZAJN ---
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
    [data-testid="stFileUploader"] button { background-color: #000000 !important; color: #ffffff !important; font-weight: bold !important; }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important;
        color: white !important;
        border-radius: 50px !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- IZBORNIK U SIDEBARU ---
st.sidebar.title("🐼 Panda Izbornik")
izbor = st.sidebar.radio("Odaberi verziju:", ["Glavni Konverter", "HPB/RBA Specijal"])

# --- ZAJEDNIČKE FUNKCIJE ---
def extract_date(text):
    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
    return match.group(1) if match else "-"

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
        val = tx['Duguje'] if tx['Duguje'] != "0.00" else tx['Potražuje']
        ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = str(val)
        cdtr = ET.SubElement(tx_inf, "{%s}Cdtr" % ns)
        ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv']
        rmt = ET.SubElement(tx_inf, "{%s}RmtInf" % ns)
        ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"
    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# --- LOGIKA ZA STRANICE ---
if izbor == "Glavni Konverter":
    st.title("📄 Glavni Konverter")
    uploaded_file = st.file_uploader("Povucite PDF ovdje", type="pdf", key="glavni")
    
    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        
        lines =
        iban_pattern = re.compile(r'HR\d{19}')
        amount_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')
        
        data = []
        for i, line in enumerate(lines):
            if iban_pattern.search(line.replace(" ", "")):
                iban = iban_pattern.search(line.replace(" ", "")).group(0)
                amount, naziv = 0.0, "Partner"
                for offset in range(-2, 4):
                    if 0 <= i + offset < len(lines):
                        s_line = lines[i+offset]
                        ams = amount_pattern.findall(s_line)
                        if ams and amount == 0.0: amount = float(ams[0].replace('.', '').replace(',', '.'))
                        if naziv == "Partner" and len(s_line) > 3 and not any(c.isdigit() for c in s_line): naziv = s_line
                if amount > 0:
                    data.append({"Datum": extract_date(text), "Konto": "2221", "Naziv": naziv[:35], "IBAN": iban, "Duguje": "{:.2f}".format(amount), "Potražuje": "0.00"})
        
        if data:
            ukupno = sum(float(tx["Duguje"]) for tx in data)
            if "0,40" in text:
                data.append({"Datum": data[0]["Datum"], "Konto": "4650", "Naziv": "Naknada", "IBAN": "", "Duguje": "0.40", "Potražuje": "0.00"})
                ukupno += 0.40
            data.append({"Datum": data[0]["Datum"], "Konto": "1000", "Naziv": "Izvod", "IBAN": "", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno)})
            st.table(data)
            st.download_button("⬇️ Preuzmi HUB3", generate_hub3(data), "izvod.hub3")

else:
    st.title("🐼 Specijalni Konverter (HPB/RBA)")
    st.info("Ovdje možete isprobavati nove promjene.")
    # Tu možete dodati novi kod kasnije...
