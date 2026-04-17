import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. POSTAVKE STRANICE I DIZAJN
st.set_page_config(page_title="Lucced PDF Konverter", page_icon="🏦", layout="centered")

# CSS za hover animacije
st.markdown("""
    <style>
    [data-testid="stFileUploader"] {
        transition: all 0.4s ease-in-out;
        border: 2px dashed #4e73df;
        border-radius: 15px;
        padding: 10px;
    }
    [data-testid="stFileUploader"]:hover {
        transform: scale(1.01);
        border-color: #ff4b4b;
        box-shadow: 0px 10px 25px rgba(0,0,0,0.15);
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF file u XML, HUB3 file")

# 2. FUNKCIJA ZA GENERIRANJE XML-a
def generate_lucced_xml(transactions):
    root = ET.Element("Document", {"xmlns": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"})
    initn = ET.SubElement(root, "CstmrCdtTrfInitn")
    
    grphdr = ET.SubElement(initn, "GrpHdr")
    ET.SubElement(grphdr, "MsgId").text = f"LUCCED-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "CreDtTm").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "NbOfTxs").text = str(len(transactions))
    
    pmt_inf = ET.SubElement(initn, "PmtInf")
    
    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
        amt = ET.SubElement(tx_inf, "Amt")
        ET.SubElement(amt, "InstdAmt", {"Ccy": "EUR"}).text = str(tx['Duguje'] if tx['Duguje'] != "0.00" else tx['Potražuje'])
        
        cdtr = ET.SubElement(tx_inf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = tx['Naziv']
        
        rmt = ET.SubElement(tx_inf, "RmtInf")
        ET.SubElement(rmt, "Ustrd").text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"

    output = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output.getvalue()

# 3. GLAVNA LOGIKA
uploaded_file = st.file_uploader("Odaberite RBA izvadak (PDF)", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            lines = [l.strip() for l in full_text.split('\n') if l.strip()]

        tablica_lucced = []
        ukupno_duguje = 0.0
        
        # --- 1. REDAK: Partner (Konto 2221) ---
        amount_match = re.search(r'D\s+([\d\.]+,\d{2})', full_text)
        iban_match = re.search(r'HR\d{19}', full_text.replace(" ", ""))
        
        if amount_match and iban_match:
            iznos = float(amount_match.group(1).replace('.', '').replace(',', '.'))
            if iznos > 1.0:
                naziv = "Nepoznato"
                for i, line in enumerate(lines):
                    if iban_match.group(0) in line.replace(" ", ""):
                        if i+1 < len(lines): naziv = lines[i+1].strip()
                        break
                
                tablica_lucced.append({"Konto": "2221", "Partner": "503", "Naziv": naziv, "Duguje": "{:.2f}".format(iznos), "Potražuje": "0.00"})
                ukupno_duguje += iznos

        # --- 2. REDAK: Naknada (Konto 4650) ---
        if "Naknada" in full_text:
            fee_match = re.search(r'D\s+0,40', full_text)
            if fee_match:
                tablica_lucced.append({"Konto": "4650", "Partner": "1", "Naziv": "Naknada - EURO NKS plaćanje", "Duguje": "0.40", "Potražuje": "0.00"})
                ukupno_duguje += 0.40

        # --- 3. REDAK: IZVOD (Konto 1000) ---
        # Ovaj redak zatvara knjiženje i stavlja ukupni iznos na Potražuje
        if tablica_lucced:
            tablica_lucced.append({
                "Konto": "1000", 
                "Partner": "", 
                "Naziv": "Izvod", 
                "Duguje": "0.00", 
                "Potražuje": "{:.2f}".format(ukupno_duguje)
            })

        # 4. PRIKAZ I DOWNLOAD
        if tablica_lucced:
            st.success("✅ Tablica spremna za Lucced:")
            st.table(tablica_lucced) 
            
            xml_data = generate_lucced_xml(tablica_lucced)
            st.download_button(label="⬇️ Preuzmi XML, HUB3 file", data=xml_data, file_name="izvod_lucced.xml")

    except Exception as e:
        st.error(f"Greška: {e}")
