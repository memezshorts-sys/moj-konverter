import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. POSTAVKE STRANICE I NAPREDNI DIZAJN (CSS)
st.set_page_config(page_title="Lucced Konverter", page_icon="🏦", layout="centered")

st.markdown("""
    <style>
    /* Pozadina cijele stranice */
    .stApp {
        background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%);
    }

    /* Postavljanje SVEGA teksta na bijelu boju */
    html, body, [class*="st-"] {
        color: #ffffff !important;
    }

    /* Posebno za naslove i podnaslove */
    h1, h2, h3, p, span, label {
        color: #ffffff !important;
    }

    /* Animacija naslova */
    h1 {
        color: #00d2ff !important; /* Naslov ostavljamo u svijetlo plavoj radi kontrasta */
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        animation: fadeInDown 1s ease-in-out;
    }

    /* Stil polja za upload */
    [data-testid="stFileUploader"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 2px dashed #00d2ff;
        border-radius: 20px;
        padding: 20px;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    [data-testid="stFileUploader"]:hover {
        transform: scale(1.02);
        border-color: #00ff88;
        background-color: rgba(255, 255, 255, 0.1);
        box-shadow: 0px 15px 30px rgba(0,0,0,0.4);
    }

    /* Gumb za download */
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white !important;
        border: none;
        padding: 15px 30px;
        border-radius: 50px;
        font-weight: bold;
        transition: all 0.3s ease;
        width: 100%;
        box-shadow: 0 4px 15px rgba(0, 210, 255, 0.3);
    }
    .stDownloadButton button:hover {
        transform: translateY(-3px);
        background: linear-gradient(90deg, #3a7bd5 0%, #00d2ff 100%);
    }

    /* Info poruka na dnu - bijeli tekst */
    .stAlert {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
        border-radius: 15px !important;
    }

    /* Animacije */
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
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
        
        # 1. Partner (2221)
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

        # 2. Naknada (4650)
        if "Naknada" in full_text:
            fee_match = re.search(r'D\s+0,40', full_text)
            if fee_match:
                tablica_lucced.append({"Konto": "4650", "Partner": "1", "Naziv": "Naknada - EURO NKS plaćanje", "Duguje": "0.40", "Potražuje": "0.00"})
                ukupno_duguje += 0.40

        # 3. Izvod (1000)
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
    # OVDJE JE BIJELI TEKST NA DNU
    st.info("💡 Ubacite PDF datoteku iznad kako biste započeli obradu.")
