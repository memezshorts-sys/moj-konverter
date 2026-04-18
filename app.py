import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. Postavke stranice
st.set_page_config(page_title="Panda Multi-Bank", page_icon="🐼", layout="centered")

# --- DIZAJN I STILIZACIJA ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    button[kind="headerNoPadding"] { background-color: #00d2ff !important; color: black !important; border-radius: 50% !important; z-index: 999999 !important; }
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
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] h1 { color: #ffffff !important; font-weight: bold !important; }
    div[data-baseweb="select"] > div { background-color: #2d3436 !important; color: white !important; border: 1px solid #00d2ff !important; }
    ul[role="listbox"] { background-color: #2d3436 !important; }
    li[role="option"] { background-color: #2d3436 !important; color: white !important; }
    li[role="option"]:hover { background-color: #00d2ff !important; color: black !important; }
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    [data-testid="stFileUploader"] { background-color: #d1d1d1 !important; border-radius: 15px !important; padding: 30px !important; }
    [data-testid="stFileUploader"] section div { color: #1e1e2f !important; }
    .stDownloadButton button { background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important; color: white !important; border-radius: 50px !important; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- IZBORNIK ---
st.sidebar.title("🐼 Panda Postavke")
opcija = st.sidebar.radio("Odaberi banku:", ("Univerzalni Konverter", "HPB Specijal", "RBA Specijal"))

st.title(f"📄 {opcija}")

# --- LOGIKA ISČITAVANJA (Univerzalni, HPB i RBA) ---
def extract_all_data(pdf_file, tip_konvertera):
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
        if iban_pattern.search(clean_line):
            iban = iban_pattern.search(clean_line).group(0)
            amount, naziv, datum = 0.0, "Nepoznati Partner", "-"
            
            # --- PRILAGODBA PRETRAGE PREMA BANCI ---
            if tip_konvertera == "HPB Specijal":
                search_range = range(-4, 6) # HPB je "razvučen"
            elif tip_konvertera == "RBA Specijal":
                search_range = range(-2, 5) # RBA je obično zbijeniji
            else:
                search_range = range(-2, 4) # Univerzalno

            for offset in search_range:
                if 0 <= i + offset < len(lines):
                    s_line = lines[i+offset]
                    
                    # Traženje iznosa
                    ams = amount_pattern.findall(s_line)
                    for am in ams:
                        val = float(am.replace('.', '').replace(',', '.'))
                        if val > 0.01: amount = val
                    
                    # Traženje datuma
                    d_match = date_pattern.search(s_line)
                    if d_match: datum = d_match.group(1)
                    
                    # Traženje naziva
                    if naziv == "Nepoznati Partner" and len(s_line) > 3:
                        if not any(c.isdigit() for c in s_line) and "HR" not in s_line:
                            naziv = s_line

            if amount > 0:
                detected_transactions.append({
                    "Datum": datum, "Konto": "2221", "Naziv": naziv[:35],
                    "IBAN": iban, "Duguje": "{:.2f}".format(amount).replace('.', ','), "Potražuje": "0,00"
                })
                
    return detected_transactions, text

# --- POMOĆNE FUNKCIJE ---
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
up_file = st.file_uploader("Povucite PDF izvadak ovdje", type="pdf")
if up_file:
    try:
        data, raw_text = extract_all_data(up_file, opcija)
        if data:
            suma = sum(float(tx["Duguje"].replace(',', '.')) for tx in data)
            current_date = data[0]["Datum"] if data[0]["Datum"] != "-" else datetime.now().strftime('%d.%m.%Y')
            
            # Automatska naknada (univerzalna provjera)
            if "0,40" in raw_text:
                data.append({"Datum": current_date, "Konto": "4650", "Naziv": "Naknada banke", "IBAN": "", "Duguje": "0,40", "Potražuje": "0,00"})
                suma += 0.40
            
            data.append({"Datum": current_date, "Konto": "1000", "Naziv": "Izvod", "IBAN": "", "Duguje": "0,00", "Potražuje": "{:.2f}".format(suma).replace('.', ',')})
            
            st.table(data)
            hub3_res = generate_hub3([t for t in data if t["Konto"] != "1000"])
            st.download_button("⬇️ Preuzmi HUB3", hub3_res, f"izvod_{opcija.replace(' ', '_').lower()}.hub3")
        else:
            st.warning("Nije pronađeno ništa u PDF-u.")
    except Exception as e:
        st.error(f"Greška: {e}")
