import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- 1. DIZAJN I STILIZACIJA (Panda stil) ---
st.set_page_config(page_title="Panda Univerzalni Konverter", page_icon="🐼", layout="centered")

st.markdown("""
    <style>
    /* Pozadina cijele stranice */
    .stApp { background: linear-gradient(135deg, #1e1e2f 0%, #2d3436 100%); }
    
    /* Vodeni žig */
    .stApp::before {
        content: 'Panda knjigovodstvo';
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%) rotate(-30deg);
        font-size: 5rem; font-weight: bold;
        color: rgba(255, 255, 255, 0.03);
        pointer-events: none; z-index: 0;
    }

    /* Svi tekstovi bijeli */
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }

    /* Prozirni Upload pravokutnik (BEZ BIJELOG LAYERA) */
    [data-testid="stFileUploader"] {
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 2px dashed #00d2ff !important;
        border-radius: 20px !important;
        padding: 60px 20px !important;
        min-height: 280px !important;
        transition: all 0.4s ease-in-out;
    }
    [data-testid="stFileUploader"] section { background-color: transparent !important; }
    
    /* Unutarnji gumb 'Browse files' */
    [data-testid="stFileUploader"] button {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border: 1px solid rgba(0, 210, 255, 0.5) !important;
    }

    /* POPRAVAK VIDLJIVOSTI NAKON UPLOADA */
    /* Ime filea - bijelo i uočljivo */
    [data-testid="stFileUploaderFileName"] {
        color: #ffffff !important;
        font-weight: bold !important;
        font-size: 1.1rem !important;
    }

    /* X gumb za micanje - crven i vidljiv */
    [data-testid="stFileUploaderDeleteBtn"] {
        color: #ff4b4b !important;
    }
    [data-testid="stFileUploaderDeleteBtn"]:hover {
        color: #ff0000 !important;
        transform: scale(1.2);
    }

    /* Hover efekt na pravokutnik */
    [data-testid="stFileUploader"]:hover {
        transform: scale(1.01);
        border-color: #00ff88 !important;
        background-color: rgba(255, 255, 255, 0.07) !important;
    }

    /* Stil gumba za download */
    .stDownloadButton button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white !important;
        border: none; border-radius: 50px;
        padding: 15px 35px; font-weight: bold;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF file u XML, HUB3 file")
st.write("### Univerzalna obrada za Panda knjigovodstvo")

# --- 2. GENERIRANJE STROGOG HUB3 XML-a ---
def generate_lucced_hub3(transactions):
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    ET.register_namespace('', ns)
    root = ET.Element("{%s}Document" % ns)
    initn = ET.SubElement(root, "{%s}CstmrCdtTrfInitn" % ns)
    
    grphdr = ET.SubElement(initn, "{%s}GrpHdr" % ns)
    ET.SubElement(grphdr, "{%s}MsgId" % ns).text = f"PANDA-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "{%s}CreDtTm" % ns).text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "{%s}NbOfTxs" % ns).text = str(len(transactions))
    
    pmt_inf = ET.SubElement(initn, "{%s}PmtInf" % ns)
    ET.SubElement(pmt_inf, "{%s}PmtInfId" % ns).text = "ISPLATA-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, "{%s}PmtMtd" % ns).text = "TRF"
    
    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, "{%s}CdtTrfTxInf" % ns)
        p_id = ET.SubElement(tx_inf, "{%s}PmtId" % ns)
        ET.SubElement(p_id, "{%s}EndToEndId" % ns).text = "HR99"
        amt = ET.SubElement(tx_inf, "{%s}Amt" % ns)
        val = tx['Duguje'] if tx['Duguje'] != "0.00" else tx['Potražuje']
        ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = str(val)
        cdtr = ET.SubElement(tx_inf, "{%s}Cdtr" % ns)
        ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv'][:70]
        rmt = ET.SubElement(tx_inf, "{%s}RmtInf" % ns)
        ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"

    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# --- 3. UNIVERZALNA EKSTRAKCIJA ---
def parse_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    
    lines =
    tablica = []
    ukupno = 0.0
    
    # Pronalazi IBAN i iznose
    iban_pattern = re.compile(r'HR\d{19}')
    amount_pattern = re.compile(r'(\d+[\d\.]*,\d{2})')

    for i, line in enumerate(lines):
        clean_line = line.replace(" ", "")
        iban_match = iban_pattern.search(clean_line)
        
        if iban_match:
            iban = iban_match.group(0)
            amount = 0.0
            naziv = "Partner"
            
            # Gledamo okolne redove za iznos i naziv
            for off in range(-1, 4):
                if 0 <= i + off < len(lines):
                    search_line = lines[i+off]
                    am_matches = amount_pattern.findall(search_line)
                    for am in am_matches:
                        v = float(am.replace('.', '').replace(',', '.'))
                        if v > 1.0 and amount == 0.0:
                            amount = v; break
                    if naziv == "Partner" and len(search_line) > 3 and "HR" not in search_line:
                        naziv = search_line

            if amount > 0:
                tablica.append({"Konto": "2221", "Naziv": naziv[:35], "Duguje": "{:.2f}".format(amount), "Potražuje": "0.00"})
                ukupno += amount

    if tablica:
        if "0,40" in text:
            tablica.append({"Konto": "4650", "Naziv": "Naknada banke", "Duguje": "0.40", "Potražuje": "0.00"})
            ukupno += 0.40
        tablica.append({"Konto": "1000", "Naziv": "Izvod", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno)})
        
    return tablica

# --- 4. WEB SUČELJE ---
uploaded_file = st.file_uploader("Povucite bilo koji PDF izvadak (ZABA, PBZ, RBA, HPB...)", type="pdf")

if uploaded_file:
    try:
        rezultat = parse_pdf(uploaded_file)
        if rezultat:
            st.success(f"Analiza završena za datoteku: {uploaded_file.name}")
            st.table(rezultat)
            
            hub3_data = generate_lucced_hub3(rezultat)
            st.download_button(
                label="⬇️ Preuzmi .hub3 datoteku",
                data=hub3_data,
                file_name=f"panda_{datetime.now().strftime('%H%M%S')}.hub3",
                mime="application/octet-stream"
            )
        else:
            st.warning("Nije pronađena niti jedna transakcija.")
    except Exception as e:
        st.error(f"Greška: {e}")
