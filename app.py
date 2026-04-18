import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I STILIZACIJA ---
st.set_page_config(page_title="Panda Lucced Konverter", page_icon="🐼", layout="centered")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    .stApp::before {
        content: 'PANDA KNJIGOVODSTVO';
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%) rotate(-30deg);
        font-size: 8vw; font-weight: 900;
        color: rgba(255, 255, 255, 0.04);
        white-space: nowrap; pointer-events: none; z-index: 0;
        letter-spacing: 15px; text-transform: uppercase;
    }
    .block-container { position: relative; z-index: 1; }
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    [data-testid="stFileUploader"] {
        background-color: #d1d1d1 !important;
        border: 2px solid #a0a0a0 !important;
        border-radius: 15px !important;
        padding: 30px !important;
    }
    [data-testid="stFileUploader"] button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: bold !important;
    }
    [data-testid="stFileUploader"] section div { color: #1e1e2f !important; }
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important;
        color: white !important;
        border-radius: 50px !important;
        font-weight: bold !important;
        border: none !important;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🐼 Panda -> Lucced Optimizer")
st.write("### Pripremite PDF za automatski uvoz")

# --- 2. OPTIMIZIRANA EKSTRAKCIJA ---
def clean_text(text):
    """Čisti nazive za XML kompatibilnost."""
    return re.sub(r'[^\w\s\-]', '', text).strip()

def extract_all_transactions(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    
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
            
            # Naprednije pretraživanje iznosa i naziva u okolini IBAN-a
            for offset in range(-3, 4):
                if 0 <= i + offset < len(lines):
                    search_line = lines[i+offset]
                    # Traženje iznosa
                    am_matches = amount_pattern.findall(search_line)
                    for am in am_matches:
                        val = float(am.replace('.', '').replace(',', '.'))
                        if val > 0.05 and amount == 0.0:
                            amount = val
                    # Traženje naziva (ako nije IBAN i nema brojeva)
                    if naziv == "Nepoznati Partner" and len(search_line) > 2:
                        if not any(char.isdigit() for char in search_line) and "HR" not in search_line:
                            naziv = clean_text(search_line)

            if amount > 0:
                detected_transactions.append({
                    "Konto": "2221",
                    "Naziv": naziv[:70], # Lucced podržava duže nazive
                    "IBAN": iban,
                    "Iznos": round(amount, 2)
                })
    
    return detected_transactions, text

# --- 3. OPTIMIZIRANI XML ZA LUCCED (pain.001.001.03) ---
def generate_pain001(transactions):
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    ET.register_namespace('', ns)
    
    root = ET.Element("{%s}Document" % ns)
    cstmr = ET.SubElement(root, "{%s}CstmrCdtTrfInitn" % ns)
    
    # Group Header
    grphdr = ET.SubElement(cstmr, "{%s}GrpHdr" % ns)
    ET.SubElement(grphdr, "{%s}MsgId" % ns).text = f"PANDA-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "{%s}CreDtTm" % ns).text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "{%s}NbOfTxs" % ns).text = str(len(transactions))
    ET.SubElement(grphdr, "{%s}CtrlSum" % ns).text = "{:.2f}".format(sum(t['Iznos'] for t in transactions))
    
    initg_pty = ET.SubElement(grphdr, "{%s}InitgPty" % ns)
    ET.SubElement(initg_pty, "{%s}Nm" % ns).text = "PANDA KONVERTER"

    # Payment Information
    pmt_inf = ET.SubElement(cstmr, "{%s}PmtInf" % ns)
    ET.SubElement(pmt_inf, "{%s}PmtInfId" % ns).text = "LUCCED-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, "{%s}PmtMtd" % ns).text = "TRF"
    ET.SubElement(pmt_inf, "{%s}NbOfTxs" % ns).text = str(len(transactions))
    
    # Requested Execution Date
    ET.SubElement(pmt_inf, "{%s}ReqdExctnDt" % ns).text = datetime.now().strftime('%Y-%m-%d')
    
    # Debtor (Ovo Lucced koristi za prepoznavanje računa platitelja)
    dbtr = ET.SubElement(pmt_inf, "{%s}Dbtr" % ns)
    ET.SubElement(dbtr, "{%s}Nm" % ns).text = "VLASTITI RACUN"
    
    # Transaction Loop
    for tx in transactions:
        cdt_tx = ET.SubElement(pmt_inf, "{%s}CdtTrfTxInf" % ns)
        pmt_id = ET.SubElement(cdt_tx, "{%s}PmtId" % ns)
        ET.SubElement(pmt_id, "{%s}EndToEndId" % ns).text = f"REF-{datetime.now().strftime('%M%S%f')[:8]}"
        
        amt = ET.SubElement(cdt_tx, "{%s}Amt" % ns)
        ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = "{:.2f}".format(tx['Iznos'])
        
        cdtr = ET.SubElement(cdt_tx, "{%s}Cdtr" % ns)
        ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv']
        
        cdtr_acct = ET.SubElement(cdt_tx, "{%s}CdtrAcct" % ns)
        id_tag = ET.SubElement(cdtr_acct, "{%s}Id" % ns)
        ET.SubElement(id_tag, "{%s}IBAN" % ns).text = tx['IBAN']
        
        rmt = ET.SubElement(cdt_tx, "{%s}RmtInf" % ns)
        ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"Uvoz Lucced | {tx['Naziv']}"

    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# --- 4. UI ---
uploaded_file = st.file_uploader("Povucite PDF izvadak za Lucced", type="pdf")

if uploaded_file:
    try:
        data, _ = extract_all_transactions(uploaded_file)
        if data:
            st.success(f"Pronađeno {len(data)} transakcija spremnih za Lucced.")
            st.table(data)
            
            final_xml = generate_pain001(data)
            st.download_button(
                label="⬇️ Preuzmi OPTIMIZIRANI XML za Lucced",
                data=final_xml,
                file_name=f"lucced_import_{datetime.now().strftime('%d%m_%H%M')}.xml",
                mime="application/xml"
            )
        else:
            st.warning("Nisu pronađeni IBAN-ovi ili iznosi.")
    except Exception as e:
        st.error(f"Sustavna greška: {e}")
