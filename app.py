import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io
import zipfile  # Modul za izradu ZIP arhive

# 1. DIZAJN STRANICE (Zadržavamo tvoj Panda stil)
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
    }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white !important;
        border-radius: 50px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF file u ZIP (XML, HUB3)")
st.write("### Sigurno preuzimanje bez automatskog otvaranja u Edgeu")

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

uploaded_file = st.file_uploader("Povucite PDF izvadak ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        tablica_lucced = []
        ukupno_duguje = 0.0

        # Logika prepoznavanja (HPB/RBA)
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
                    tablica_lucced.append({
                        "Konto": "2221", "Partner": "503", "Naziv": naziv[:30], 
                        "Duguje": "{:.2f}".format(found_amount), "Potražuje": "0.00"
                    })
                    ukupno_duguje += found_amount

        if tablica_lucced:
            tablica_lucced.append({"Konto": "1000", "Partner": "", "Naziv": "Izvod", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno_duguje)})
            
            st.success("✅ Podaci isčitani!")
            st.table(tablica_lucced)
            
            # --- STVARANJE ZIP ARHIVE ---
            xml_bytes = generate_lucced_xml(tablica_lucced)
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                # Upisujemo XML u ZIP (naziv datoteke unutar ZIP-a)
                zf.writestr("nalog_za_lucced.xml", xml_bytes)
            
            # Gumb za preuzimanje ZIP datoteke
            st.download_button(
                label="⬇️ Preuzmi ZIP arhivu (XML unutra)",
                data=zip_buffer.getvalue(),
                file_name=f"izvod_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip"
            )
            st.balloons()

    except Exception as e:
        st.error(f"Greška: {e}")
