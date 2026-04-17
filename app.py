import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. DIZAJN I POSTAVKE
st.set_page_config(page_title="Panda Konverter", page_icon="🐼", layout="centered")

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
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 2px dashed #00d2ff !important;
        border-radius: 20px !important;
        padding: 50px 20px !important;
        min-height: 250px !important;
        transition: all 0.4s ease-in-out;
    }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white !important;
        border-radius: 50px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF file u XML, HUB3 file")
st.write("### Univerzalna obrada bankovnih izvoda")

def generate_lucced_xml(transactions):
    root = ET.Element("Document", {"xmlns": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"})
    initn = ET.SubElement(root, "CstmrCdtTrfInitn")
    grphdr = ET.SubElement(initn, "GrpHdr")
    ET.SubElement(grphdr, "MsgId").text = f"LUCCED-{datetime.now().strftime('%Y%m%d%H%M%S')}"
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

# --- UNIVERZALNI PARSER ---
def parse_any_pdf(full_text):
    lines = [l.strip() for l in full_text.split('\n') if l.strip()]
    data = {"iban": "", "amount": 0.0, "recipient": "Nepoznato", "banka": "Nepoznato"}
    
    # Detekcija banke
    if "RAIFFEISEN" in full_text.upper(): data["banka"] = "RBA"
    elif "HRVATSKA POŠTANSKA BANKA" in full_text.upper() or "HPB" in full_text.upper(): data["banka"] = "HPB"

    # 1. Traženje IBAN-a (Univerzalno)
    iban_match = re.search(r'HR\d{19}', full_text.replace(" ", ""))
    if iban_match:
        data["iban"] = iban_match.group(0)
        # Traženje imena oko IBAN-a
        for i, line in enumerate(lines):
            if data["iban"] in line.replace(" ", ""):
                # Kod RBA je ime ispod, kod HPB je često iznad ili pored
                if data["banka"] == "RBA" and i + 1 < len(lines):
                    data["recipient"] = lines[i+1]
                else:
                    data["recipient"] = lines[i-1] if i > 0 else "Partner"
                break

    # 2. Traženje IZNOSA
    # Tražimo format 'D 100,00' ili samo '100,00' uz uvjet da je veći od 1.0
    amounts = re.findall(r'(?:D\s+)?(\d+[\d\.]*,\d{2})', full_text)
    for am in amounts:
        val = float(am.replace('.', '').replace(',', '.'))
        if val > 1.0: # Preskačemo naknade u ovom koraku
            data["amount"] = val
            break
            
    return data

uploaded_file = st.file_uploader("Povucite bilo koji PDF izvadak ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        parsed = parse_any_pdf(full_text)
        tablica_lucced = []
        ukupno_duguje = 0.0

        if parsed["iban"] and parsed["amount"] > 0:
            # 1. Partner
            tablica_lucced.append({
                "Konto": "2221", "Partner": "503", "Naziv": parsed["recipient"],
                "Duguje": "{:.2f}".format(parsed["amount"]), "Potražuje": "0.00"
            })
            ukupno_duguje += parsed["amount"]

            # 2. Naknada (Automatski detektira 0,40 ako postoji)
            if "0,40" in full_text:
                tablica_lucced.append({
                    "Konto": "4650", "Partner": "1", "Naziv": "Naknada banke",
                    "Duguje": "0.40", "Potražuje": "0.00"
                })
                ukupno_duguje += 0.40

            # 3. Izvod
            tablica_lucced.append({
                "Konto": "1000", "Partner": "", "Naziv": f"Izvod - {parsed['banka']}",
                "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno_duguje)
            })

            st.markdown(f"### 📊 Detektirana banka: {parsed['banka']}")
            st.table(tablica_lucced)
            
            xml_data = generate_lucced_xml(tablica_lucced)
            st.download_button(label="⬇️ Preuzmi XML, HUB3 file", data=xml_data, file_name=f"izvod_{parsed['banka']}.xml")
            st.balloons()
        else:
            st.warning("Nisam uspio isčitati ključne podatke (IBAN ili Iznos). Provjerite PDF.")

    except Exception as e:
        st.error(f"Greška pri obradi: {e}")
else:
    st.info("💡 Sustav automatski prepoznaje banku i strukturira podatke za Lucced.")
