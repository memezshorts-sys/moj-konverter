import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I STILIZACIJA (Panda stil) ---
st.set_page_config(page_title="Panda Univerzalni Konverter", page_icon="🐼", layout="centered")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    .stApp::before {
        content: 'Panda knjigovodstvo';
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%) rotate(-30deg);
        font-size: 5rem; font-weight: bold;
        color: rgba(255, 255, 255, 0.03);
        pointer-events: none; z-index: 0;
    }
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    [data-testid="stFileUploader"] {
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 2px dashed #00d2ff !important;
        border-radius: 20px !important;
        padding: 60px 20px !important;
        min-height: 280px !important;
    }
    [data-testid="stFileUploader"] section { background-color: transparent !important; }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white !important;
        border-radius: 50px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 Univerzalni PDF u HUB3")
st.write("### Automatska analiza bilo kojeg bankovnog izvatka")

# --- 2. UNIVERZALNA FUNKCIJA ZA EKSTRAKCIJU ---
def extract_all_transactions(pdf_file):
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Tražimo sve IBAN-ove i iznose u blizini (RegEx)
    # Pronalazi HR + 19 znamenki
    iban_pattern = re.compile(r'HR\d{19}')
    # Pronalazi iznose u formatu 1.234,56 ili 123,45
    amount_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')

    detected_transactions = []
    
    for i, line in enumerate(lines):
        clean_line = line.replace(" ", "")
        iban_match = iban_pattern.search(clean_line)
        
        if iban_match:
            iban = iban_match.group(0)
            amount = 0.0
            naziv = "Nepoznati Partner"
            
            # Gledamo okolne redove (-2 do +3) za iznos i naziv
            for offset in range(-2, 4):
                if 0 <= i + offset < len(lines):
                    search_line = lines[i+offset]
                    
                    # Tražimo iznos
                    am_matches = amount_pattern.findall(search_line)
                    for am in am_matches:
                        val = float(am.replace('.', '').replace(',', '.'))
                        # Filtriramo naknade (često su 0,40 ili slično) i uzimamo prvi veći iznos
                        if val > 1.0 and amount == 0.0:
                            amount = val
                    
                    # Tražimo naziv (ako linija ne sadrži IBAN ili brojeve, vjerojatno je ime)
                    if naziv == "Nepoznati Partner" and len(search_line) > 3:
                        if not any(char.isdigit() for char in search_line) and "HR" not in search_line:
                            naziv = search_line

            if amount > 0:
                detected_transactions.append({
                    "Konto": "2221",
                    "Naziv": naziv[:35],
                    "IBAN": iban,
                    "Duguje": "{:.2f}".format(amount),
                    "Potražuje": "0.00"
                })
    
    return detected_transactions, text

# --- 3. GENERIRANJE HUB3 ---
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

# --- 4. WEB SUČELJE ---
uploaded_file = st.file_uploader("Povucite bilo koji PDF izvadak (ZABA, PBZ, RBA, HPB...)", type="pdf")

if uploaded_file:
    try:
        data, raw_text = extract_all_transactions(uploaded_file)
        
        if data:
            ukupno = sum(float(tx["Duguje"]) for tx in data)
            
            # Detekcija naknade (ako postoji 0,40 ili slično u tekstu)
            if "0,40" in raw_text:
                data.append({"Konto": "4650", "Naziv": "Naknada banke", "IBAN": "", "Duguje": "0.40", "Potražuje": "0.00"})
                ukupno += 0.40
            
            # Zadnji redak: Izvod (Konto 1000)
            data.append({"Konto": "1000", "Naziv": "Izvod", "IBAN": "", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno)})
            
            st.success(f"Analiza završena! Pronađeno transakcija: {len(data)-2}")
            st.table(data)
            
            hub3_data = generate_hub3(data)
            st.download_button(
                label="⬇️ Preuzmi HUB3 datoteku",
                data=hub3_data,
                file_name=f"panda_izvod_{datetime.now().strftime('%H%M%S')}.hub3",
                mime="application/octet-stream"
            )
        else:
            st.warning("Nije pronađena nijedna transakcija. Provjerite je li PDF digitalno generiran (ne skeniran).")
            
    except Exception as e:
        st.error(f"Greška pri obradi: {e}")
