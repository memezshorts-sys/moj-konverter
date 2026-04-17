import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io
import zipfile

# 1. DIZAJN STRANICE
st.set_page_config(page_title="Panda Lucced Konverter", page_icon="🐼", layout="centered")

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

st.title("📄 PDF u HUB3 file (Lucced)")

def generate_hub3_content(transactions):
    """Generira sadržaj optimiziran za Lucced uvoz."""
    # Stvaramo bazu za HUB3 XML (pain.001.001.03)
    root = ET.Element("Document", {"xmlns": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"})
    initn = ET.SubElement(root, "CstmrCdtTrfInitn")
    
    grphdr = ET.SubElement(initn, "GrpHdr")
    ET.SubElement(grphdr, "MsgId").text = f"HUB3-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "CreDtTm").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "NbOfTxs").text = str(len(transactions))
    
    pmt_inf = ET.SubElement(initn, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = "NALOG-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, "PmtMtd").text = "TRF"
    
    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
        p_id = ET.SubElement(tx_inf, "PmtId")
        ET.SubElement(p_id, "EndToEndId").text = "HR99"
        
        amt = ET.SubElement(tx_inf, "Amt")
        # Lucced treba točan format broja (npr. 100.40)
        ET.SubElement(amt, "InstdAmt", {"Ccy": "EUR"}).text = str(tx['Duguje'] if tx['Duguje'] != "0.00" else tx['Potražuje'])
        
        cdtr = ET.SubElement(tx_inf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = tx['Naziv'][:70] # Ograničenje duljine naziva
        
        rmt = ET.SubElement(tx_inf, "RmtInf")
        # Lucced čita KONTO iz polja svrhe ako je tako podešen
        ET.SubElement(rmt, "Ustrd").text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"

    output = io.BytesIO()
    tree = ET.ElementTree(root)
    # Dodajemo XML deklaraciju koju programi zahtijevaju
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output.getvalue()

uploaded_file = st.file_uploader("Povucite PDF izvadak ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        tablica_lucced = []
        ukupno_duguje = 0.0

        # Univerzalni parser (HPB/RBA)
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
            
            # --- ZIP PAKIRANJE ---
            hub3_bytes = generate_hub3_content(tablica_lucced)
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # Ključno: Datoteka unutar ZIP-a se zove .hub3
                zf.writestr(f"izvod_{datetime.now().strftime('%H%M%S')}.hub3", hub3_bytes)
            
            st.download_button(
                label="⬇️ Preuzmi HUB3 ZIP arhivu",
                data=zip_buffer.getvalue(),
                file_name=f"lucced_export.zip",
                mime="application/zip"
            )
    except Exception as e:
        st.error(f"Greška: {e}")
