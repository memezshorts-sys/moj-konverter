import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. DIZAJN STRANICE
st.set_page_config(page_title="Panda Lucced Fix", page_icon="🐼", layout="centered")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    [data-testid="stFileUploader"] {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 2px dashed #00d2ff !important;
        border-radius: 20px !important;
        padding: 50px 20px !important;
    }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white !important;
        border-radius: 50px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 HUB3 Konverter za Lucced")

def generate_strict_hub3(transactions):
    """Generira strogo definiran HUB3 nalog za hrvatske programe."""
    # Namespace koji koriste HR banke i programi
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    ET.register_namespace('', ns)
    
    root = ET.Element("{%s}Document" % ns)
    initn = ET.SubElement(root, "{%s}CstmrCdtTrfInitn" % ns)
    
    # 1. Group Header
    grphdr = ET.SubElement(initn, "{%s}GrpHdr" % ns)
    ET.SubElement(grphdr, "{%s}MsgId" % ns).text = f"ID-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "{%s}CreDtTm" % ns).text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "{%s}NbOfTxs" % ns).text = str(len(transactions))
    
    # Init Party (Tvoja firma/Panda)
    initgpty = ET.SubElement(grphdr, "{%s}InitgPty" % ns)
    ET.SubElement(initgpty, "{%s}Nm" % ns).text = "Panda Knjigovodstvo"

    # 2. Payment Information
    pmt_inf = ET.SubElement(initn, "{%s}PmtInf" % ns)
    ET.SubElement(pmt_inf, "{%s}PmtInfId" % ns).text = "PIID-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, "{%s}PmtMtd" % ns).text = "TRF"
    
    # Platitelj (Debtor) - Obavezno polje
    dbtr = ET.SubElement(pmt_inf, "{%s}Dbtr" % ns)
    ET.SubElement(dbtr, "{%s}Nm" % ns).text = "Vlasnik Racuna"
    
    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, "{%s}CdtTrfTxInf" % ns)
        p_id = ET.SubElement(tx_inf, "{%s}PmtId" % ns)
        ET.SubElement(p_id, "{%s}EndToEndId" % ns).text = "HR99"
        
        # Iznos
        amt = ET.SubElement(tx_inf, "{%s}Amt" % ns)
        ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = str(tx['Duguje'] if tx['Duguje'] != "0.00" else tx['Potražuje'])
        
        # Primatelj (Creditor)
        cdtr = ET.SubElement(tx_inf, "{%s}Cdtr" % ns)
        ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv'][:70]
        
        # Svrha (Ustrd) - Tu stavljamo informaciju o kontu
        rmt = ET.SubElement(tx_inf, "{%s}RmtInf" % ns)
        ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"{tx['Konto']} - {tx['Naziv']}"

    output = io.BytesIO()
    # Dodajemo XML zaglavlje s UTF-8
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

uploaded_file = st.file_uploader("Povucite PDF ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        tablica_lucced = []
        ukupno_duguje = 0.0

        # Parser
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
                file_name=f"nalog_{datetime.now().strftime('%H%M%S')}.hub3",
                mime="application/xml"
            )
            st.balloons()
            
    except Exception as e:
        st.error(f"Došlo je do greške: {e}")
