import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. DIZAJN STRANICE - BEZ BIJELOG LAYERA I S ANIMACIJAMA
st.set_page_config(page_title="Panda HUB3 Konverter", page_icon="🐼", layout="centered")

st.markdown("""
    <style>
    /* Pozadina cijele stranice */
    .stApp {
        background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%);
    }

    /* VODENI ŽIG (Panda knjigovodstvo) */
    .stApp::before {
        content: 'Panda knjigovodstvo';
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%) rotate(-30deg);
        font-size: 5rem; font-weight: bold;
        color: rgba(255, 255, 255, 0.03);
        pointer-events: none; z-index: 0;
    }

    /* SVI TEKSTOVI BIJELI */
    html, body, [class*="st-"], h1, h2, h3, p, span, label {
        color: #ffffff !important;
    }

    /* POTPUNO UKLANJANJE BIJELOG SLOJA IZ PRAVOKUTNIKA */
    [data-testid="stFileUploader"] {
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 2px dashed #00d2ff !important;
        border-radius: 20px !important;
        padding: 50px 20px !important;
        min-height: 250px !important;
        transition: all 0.4s ease-in-out;
    }

    [data-testid="stFileUploader"] section {
        background-color: transparent !important;
        border: none !important;
    }

    /* Gumb 'Browse files' */
    [data-testid="stFileUploader"] button {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border: 1px solid rgba(0, 210, 255, 0.5) !important;
    }

    /* HOVER ANIMACIJA */
    [data-testid="stFileUploader"]:hover {
        transform: scale(1.01);
        background-color: rgba(255, 255, 255, 0.07) !important;
        border-color: #00ff88 !important;
        box-shadow: 0px 0px 30px rgba(0, 210, 255, 0.2);
    }

    /* Stil gumba za download */
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white !important;
        border: none;
        border-radius: 50px;
        font-weight: bold;
        transition: 0.3s;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF file u XML, HUB3 file")
st.write("### Panda Knjigovodstvo - Brza obrada")

# 2. FUNKCIJA ZA HUB3 (PAIN.001.001.03)
def generate_strict_hub3(transactions):
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    ET.register_namespace('', ns)
    root = ET.Element("{%s}Document" % ns)
    initn = ET.SubElement(root, "{%s}CstmrCdtTrfInitn" % ns)
    
    grphdr = ET.SubElement(initn, "{%s}GrpHdr" % ns)
    ET.SubElement(grphdr, "{%s}MsgId" % ns).text = f"ID-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "{%s}CreDtTm" % ns).text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "{%s}NbOfTxs" % ns).text = str(len(transactions))
    
    pmt_inf = ET.SubElement(initn, "{%s}PmtInf" % ns)
    ET.SubElement(pmt_inf, "{%s}PmtInfId" % ns).text = "PIID-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, "{%s}PmtMtd" % ns).text = "TRF"
    
    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, "{%s}CdtTrfTxInf" % ns)
        p_id = ET.SubElement(tx_inf, "{%s}PmtId" % ns)
        ET.SubElement(p_id, "{%s}EndToEndId" % ns).text = "HR99"
        
        amt = ET.SubElement(tx_inf, "{%s}Amt" % ns)
        ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = str(tx['Duguje'] if tx['Duguje'] != "0.00" else tx['Potražuje'])
        
        cdtr = ET.SubElement(tx_inf, "{%s}Cdtr" % ns)
        ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv'][:70]
        
        rmt = ET.SubElement(tx_inf, "{%s}RmtInf" % ns)
        ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"{tx['Konto']} - {tx['Naziv']}"

    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# 3. GLAVNA LOGIKA
uploaded_file = st.file_uploader("Povucite PDF izvadak ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        tablica_lucced = []
        ukupno_duguje = 0.0

        for i, line in enumerate(lines):
            iban_match = re.search(r'HR\d{19}', line.replace(" ", ""))
            if iban_match:
                clean_iban = iban_match.group(0)
                found_amount = 0.0
                for offset in range(-1, 4):
                    if i + offset < len(lines):
                        amt_match = re.findall(r'(\d+[\d\.]*,\d{2})', lines[i+offset])
                        for a in amt_match:
                            val = float(a.replace('.', '').replace(',', '.'))
                            if val > 1.0: 
                                found_amount = val
                                break
                
                naziv = line.split(clean_iban)[-1].strip() if clean_iban in line.replace(" ","") else "Partner"
                if found_amount > 0:
                    tablica_lucced.append({"Konto": "2221", "Naziv": naziv[:30], "Duguje": "{:.2f}".format(found_amount), "Potražuje": "0.00"})
                    ukupno_duguje += found_amount

        if tablica_lucced:
            tablica_lucced.append({"Konto": "1000", "Naziv": "Izvod", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno_duguje)})
            st.table(tablica_lucced)
            
            hub3_data = generate_strict_hub3(tablica_lucced)
            st.download_button(
                label="⬇️ Preuzmi HUB3 datoteku",
                data=hub3_data,
                file_name=f"izvod_{datetime.now().strftime('%H%M%S')}.hub3",
                mime="application/xml"
            )
            # st.balloons() je uklonjen
            
    except Exception as e:
        st.error(f"Greška: {e}")
else:
    st.info("💡 Ubacite PDF datoteku iznad kako biste započeli obradu.")
