import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. POSTAVKE STRANICE I DIZAJN S VEĆIM OKVIROM
st.set_page_config(page_title="Panda Konverter", page_icon="🐼", layout="centered")

st.markdown("""
    <style>
    /* Pozadina */
    .stApp {
        background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%);
    }

    /* Vodeni žig */
    .stApp::before {
        content: 'Panda knjigovodstvo';
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) rotate(-30deg);
        font-size: 5rem;
        font-weight: bold;
        color: rgba(255, 255, 255, 0.03);
        pointer-events: none;
        z-index: 0;
    }

    /* Svi tekstovi bijeli */
    html, body, [class*="st-"], h1, h2, h3, p, span, label {
        color: #ffffff !important;
    }

    /* POVEĆAN I PROZIRAN OKVIR ZA UPLOAD */
    [data-testid="stFileUploader"] {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 2px dashed #00d2ff !important;
        border-radius: 20px !important;
        padding: 50px 20px !important; /* Povećan padding (gore/dolje) za veću površinu */
        min-height: 250px !important; /* Fiksna minimalna visina da bude prostranije */
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.4s ease-in-out;
    }

    /* Unutarnji gumb (Browse) */
    [data-testid="stFileUploader"] section button {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        padding: 10px 25px !important;
    }

    /* Hover efekt */
    [data-testid="stFileUploader"]:hover {
        transform: scale(1.01);
        border-color: #00ff88 !important;
        background-color: rgba(255, 255, 255, 0.08) !important;
    }

    /* Stil gumba za download */
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white !important;
        border-radius: 50px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF file u XML, HUB3 file")
st.write("### Brza obrada RBA izvatka za Lucced")

# 2. FUNKCIJA ZA XML
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

# 3. OBRADA DATOTEKE
uploaded_file = st.file_uploader("Povucite PDF izvadak ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        tablica_lucced = []
        ukupno_duguje = 0.0
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
        if "Naknada" in full_text:
            fee_match = re.search(r'D\s+0,40', full_text)
            if fee_match:
                tablica_lucced.append({"Konto": "4650", "Partner": "1", "Naziv": "Naknada - EURO NKS plaćanje", "Duguje": "0.40", "Potražuje": "0.00"})
                ukupno_duguje += 0.40
        if tablica_lucced:
            tablica_lucced.append({"Konto": "1000", "Partner": "", "Naziv": "Izvod", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno_duguje)})
            st.markdown("### 📊 Generirana tablica za Lucced")
            st.table(tablica_lucced)
            xml_data = generate_lucced_xml(tablica_lucced)
            st.download_button(label="⬇️ Preuzmi XML, HUB3 file", data=xml_data, file_name="izvod_lucced.xml")
            st.balloons()
    except Exception as e:
        st.error(f"Greška: {e}")
else:
    st.info("💡 Ubacite PDF datoteku iznad kako biste započeli obradu.")
