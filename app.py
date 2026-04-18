import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I STILIZACIJA (Panda stil) ---
st.set_page_config(page_title="Panda Lucced Optimiser", page_icon="🐼", layout="centered")

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
    [data-testid="stFileUploader"] {
        background-color: #d1d1d1 !important;
        border: 2px solid #a0a0a0 !important;
        border-radius: 15px !important;
        padding: 30px !important;
    }
    [data-testid="stFileUploader"] section div p { color: #000000 !important; font-weight: bold !important; }
    [data-testid="stFileUploader"] button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important;
        color: white !important; border-radius: 50px !important; width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF u Lucced XML")
st.write("### Optimizirano za izravan import u Lucced")

# --- 2. POMOĆNE FUNKCIJE ---
def clean_text(text):
    """Uklanja znakove koji mogu smetati XML importu."""
    return re.sub(r'[^\w\s\-]', '', text).strip()

def extract_all_transactions(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    iban_pattern = re.compile(r'HR\d{19}')
    amount_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')

    detected_transactions = []
    for i, line in enumerate(lines):
        clean_line = line.replace(" ", "")
        iban_match = iban_pattern.search(clean_line)
        
        if iban_match:
            iban = iban_match.group(0)
            amount = 0.0
            naziv = "Nepoznati Partner"
            
            for offset in range(-2, 4):
                if 0 <= i + offset < len(lines):
                    search_line = lines[i+offset]
                    am_matches = amount_pattern.findall(search_line)
                    for am in am_matches:
                        val = float(am.replace('.', '').replace(',', '.'))
                        if val > 1.0 and amount == 0.0: amount = val
                    if naziv == "Nepoznati Partner" and len(search_line) > 3:
                        if not any(char.isdigit() for char in search_line) and "HR" not in search_line:
                            naziv = clean_text(search_line)

            if amount > 0:
                detected_transactions.append({
                    "Konto": "2221",
                    "Naziv": naziv[:35],
                    "IBAN": iban,
                    "Iznos": "{:.2f}".format(amount)
                })
    return detected_transactions, text

# --- 3. GENERIRANJE OPTIMIZIRANOG XML-A ---
def generate_lucced_xml(transactions):
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    ET.register_namespace('', ns)
    root = ET.Element(f"{{{ns}}}Document")
    initn = ET.SubElement(root, f"{{{ns}}}CstmrCdtTrfInitn")
    
    # Group Header
    grphdr = ET.SubElement(initn, f"{{{ns}}}GrpHdr")
    ET.SubElement(grphdr, f"{{{ns}}}MsgId").text = f"LUCCED-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, f"{{{ns}}}CreDtTm").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, f"{{{ns}}}NbOfTxs").text = str(len(transactions))
    ET.SubElement(grphdr, f"{{{ns}}}CtrlSum").text = "{:.2f}".format(sum(float(tx['Iznos']) for tx in transactions))
    
    initg_pty = ET.SubElement(grphdr, f"{{{ns}}}InitgPty")
    ET.SubElement(initg_pty, f"{{{ns}}}Nm").text = "PANDA IMPORT"

    # Payment Info
    pmt_inf = ET.SubElement(initn, f"{{{ns}}}PmtInf")
    ET.SubElement(pmt_inf, f"{{{ns}}}PmtInfId").text = "NALOG-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, f"{{{ns}}}PmtMtd").text = "TRF"
    ET.SubElement(pmt_inf, f"{{{ns}}}NbOfTxs").text = str(len(transactions))
    
    tp = ET.SubElement(ET.SubElement(pmt_inf, f"{{{ns}}}PmtTpInf"), f"{{{ns}}}SvcLvl")
    ET.SubElement(tp, f"{{{ns}}}Cd").text = "SEPA"

    # Pojedinačne transakcije
    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, f"{{{ns}}}CdtTrfTxInf")
        p_id = ET.SubElement(tx_inf, f"{{{ns}}}PmtId")
        ET.SubElement(p_id, f"{{{ns}}}EndToEndId").text = "NOTPROVIDED"
        
        amt = ET.SubElement(tx_inf, f"{{{ns}}}Amt")
        ET.SubElement(amt, f"{{{ns}}}InstdAmt", {"Ccy": "EUR"}).text = tx['Iznos']
        
        # Creditor (Primatelj)
        cdtr = ET.SubElement(tx_inf, f"{{{ns}}}Cdtr")
        ET.SubElement(cdtr, f"{{{ns}}}Nm").text = tx['Naziv']
        
        # Creditor Account (IBAN)
        cdtr_acct = ET.SubElement(tx_inf, f"{{{ns}}}CdtrAcct")
        id_tag = ET.SubElement(cdtr_acct, f"{{{ns}}}Id")
        ET.SubElement(id_tag, f"{{{ns}}}IBAN").text = tx['IBAN']
        
        # Remittance Info (Poziv na broj - ključno za Lucced)
        rmt = ET.SubElement(tx_inf, f"{{{ns}}}RmtInf")
        strd = ET.SubElement(rmt, f"{{{ns}}}Strd")
        cdtr_ref = ET.SubElement(strd, f"{{{ns}}}CdtrRefInf")
        tp = ET.SubElement(cdtr_ref, f"{{{ns}}}Tp")
        issr = ET.SubElement(tp, f"{{{ns}}}CdOrPrtry")
        ET.SubElement(issr, f"{{{ns}}}Cd").text = "SCOR" # Standard za Structured
        ET.SubElement(cdtr_ref, f"{{{ns}}}Ref").text = "HR99-12345-678" # Default placeholder

    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# --- 4. WEB SUČELJE ---
uploaded_file = st.file_uploader("Povucite PDF izvadak ovdje", type="pdf")

if uploaded_file:
    data, raw_text = extract_all_transactions(uploaded_file)
    if data:
        st.success(f"Optimizirano za Lucced! Pronađeno: {len(data)} transakcija.")
        st.table(data)
        
        xml_file = generate_lucced_xml(data)
        st.download_button(
            label="⬇️ Preuzmi Lucced XML",
            data=xml_file,
            file_name=f"lucced_import_{datetime.now().strftime('%H%M%S')}.xml",
            mime="application/xml"
        )
    else:
        st.warning("Nije pronađena nijedna transakcija.")
