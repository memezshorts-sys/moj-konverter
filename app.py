import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I STILIZACIJA ---
st.set_page_config(page_title="Panda Multi-Bank", page_icon="🐼", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    .stApp::before {
        content: 'PANDA KNJIGOVODSTVO';
        position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(-30deg);
        font-size: 8vw; font-weight: 900; color: rgba(255, 255, 255, 0.04);
        pointer-events: none; z-index: 0; white-space: nowrap;
    }
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    [data-testid="stSidebar"] { background-color: #1e1e2f !important; border-right: 1px solid #00d2ff; }
    [data-testid="stFileUploader"] { background-color: #d1d1d1 !important; border-radius: 15px !important; padding: 20px !important; }
    [data-testid="stFileUploader"] section div p { color: #000000 !important; font-weight: bold !important; }
    [data-testid="stFileUploader"] button { background-color: #000000 !important; color: #ffffff !important; }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important;
        color: white !important; border-radius: 50px !important; width: 100%; border: none !important;
    }
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
            # HPB: Naziv je obično desno od IBAN-a ili u redu iznad/ispod
            naziv = line.replace(iban, "").strip()
            if len(naziv) < 3 and i+1 < len(lines):
                naziv = lines[i+1]
            
            amount = 0.0
            datum = datetime.now().strftime("%d.%m.%Y")
            
            # HPB specifično: Iznos i datum su u redovima ISPOD IBAN-a
            for offset in range(1, 5):
                if i + offset < len(lines):
                    s_line = lines[i+offset]
                    if d_m := date_pattern.search(s_line): datum = d_m.group(0)
                    if am_matches := amount_pattern.findall(s_line):
                        # Uzimamo iznos, HPB obično ima jedan iznos po transakciji u stupcu 'Duguje'
                        val = float(am_matches[0].replace('.', '').replace(',', '.'))
                        if val > 0.40: amount = val # Ignoriramo sitne naknade unutar transakcije
            
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
            # RBA: Naziv je često red iznad IBAN-a
            naziv = lines[i-1] if i > 0 else "Partner"
            if "Račun" in naziv or "Datum" in naziv: naziv = "Partner"
            
            amount = 0.0
            datum = ""
            # RBA: Iznos je obično u istom redu gdje i datum knjiženja
            for offset in range(-1, 3):
                if 0 <= i + offset < len(lines):
                    s_line = lines[i+offset]
                    if am_matches := amount_pattern.findall(s_line):
                        val = float(am_matches[-1].replace('.', '').replace(',', '.'))
                        if val > 0.40: amount = val
                    if d_m := re.search(r'\d{2}\.\d{2}\.\d{4}', s_line):
                        datum = d_m.group(0)

            results.append({"Datum": datum, "Konto": "2221", "Naziv": naziv[:35], "IBAN": iban, "Duguje": "{:.2f}".format(amount), "Potražuje": "0.00"})
    return results

# --- 3. HUB3 GENERATOR ---
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
    ET.SubElement(pmt_inf, "{%s}PmtInfId" % ns).text = "NALOG-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, "{%s}PmtMtd" % ns).text = "TRF"
    
    for tx in transactions:
        if float(tx['Duguje']) > 0:
            tx_inf = ET.SubElement(pmt_inf, "{%s}CdtTrfTxInf" % ns)
            p_id = ET.SubElement(tx_inf, "{%s}PmtId" % ns)
            ET.SubElement(p_id, "{%s}EndToEndId" % ns).text = "HR99"
            amt = ET.SubElement(tx_inf, "{%s}Amt" % ns)
            ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = tx['Duguje']
            cdtr = ET.SubElement(tx_inf, "{%s}Cdtr" % ns)
            ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv']
            rmt = ET.SubElement(tx_inf, "{%s}RmtInf" % ns)
            ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"

    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# --- 4. UI ---
with st.sidebar:
    st.title("🐼 Panda Postavke")
    banka = st.selectbox("Odaberite banku:", ["HPB", "RBA"])
    st.write("---")
    st.write("Sustav prilagođen za: **" + banka + "**")

st.title("📄 Univerzalni Konverter")

uploaded_file = st.file_uploader("Povucite PDF izvadak ovdje", type="pdf")

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        raw_text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])

    data = parse_hpb(raw_text) if banka == "HPB" else parse_rba(raw_text)

    if data:
        ukupno = sum(float(tx["Duguje"]) for tx in data)
        # Dodavanje naknade ako postoji u tekstu
        if "0,40" in raw_text:
            data.append({"Datum": data[0]["Datum"], "Konto": "4650", "Naziv": "Naknada banke", "IBAN": "", "Duguje": "0.40", "Potražuje": "0.00"})
            ukupno += 0.40
        
        data.append({"Datum": data[0]["Datum"], "Konto": "1000", "Naziv": "Izvod", "IBAN": "", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno)})
        
        st.table(data)
        
        hub3_xml = generate_hub3(data[:-1]) # Bez zadnjeg reda (Izvod)
        st.download_button("⬇️ Preuzmi HUB3", data=hub3_xml, file_name="izvod.hub3", mime="application/xml")
    else:
        st.warning("Nema podataka. Provjerite banku.")
