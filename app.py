import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. Postavke stranice - OVO MORA BITI PRVO
st.set_page_config(page_title="Panda Multi-Bank", page_icon="🐼", layout="centered")

# --- DIZAJN ---
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
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }
    [data-testid="stFileUploader"] { background-color: #d1d1d1 !important; border-radius: 15px !important; padding: 30px !important; }
    [data-testid="stFileUploader"] section div { color: #1e1e2f !important; }
    .stDownloadButton button { background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important; color: white !important; border-radius: 50px !important; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- IZBORNIK U SIDEBARU ---
st.sidebar.title("🐼 Panda Postavke")
banka = st.sidebar.selectbox(
    "Odaberite banku:",
    ("Univerzalni Konverter", "HPB", "RBA")
)

st.title(f"📄 {banka} Konverter")

# --- FUNKCIJE ---
def extract_date(text):
    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
    return match.group(1) if match else datetime.now().strftime('%d.%m.%Y')

def generate_hub3(transactions):
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    ET.register_namespace('', ns)
    root = ET.Element("{%s}Document" % ns)
    initn = ET.SubElement(root, "{%s}CstmrCdtTrfInitn" % ns)
    grphdr = ET.SubElement(initn, "{%s}GrpHdr" % ns)
    ET.SubElement(grphdr, "{%s}MsgId" % ns).text = f"ID-{datetime.now().strftime('%Y%m%d%H%M%S')}"
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
        val = tx['Duguje'].replace(',', '.')
        ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = val
        cdtr = ET.SubElement(tx_inf, "{%s}Cdtr" % ns)
        ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv']
        rmt = ET.SubElement(tx_inf, "{%s}RmtInf" % ns)
        ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"
    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# --- LOGIKA KONVERZIJE ---
up_file = st.file_uploader("Povucite PDF ovdje", type="pdf")

if up_file:
    try:
        with pdfplumber.open(up_file) as pdf:
            raw_t = "\n".join([p.extract_text() or "" for p in pdf.pages])
        
        # POPRAVLJENA LINIJA (sada u jednom redu)
        lines = [l.strip() for l in raw_t.split('\n') if l.strip()]
        
        iban_pat = re.compile(r'HR\d{19}')
        amt_pat = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')
        data = []
        glavni_datum = extract_date(raw_t)

        for i, line in enumerate(lines):
            clean_l = line.replace(" ", "")
            if iban_pat.search(clean_l):
                iban = iban_pat.search(clean_l).group(0)
                # Širi krug pretrage za specifične banke
                search_range = range(-3, 5) if banka != "Univerzalni Konverter" else range(-2, 4)
                amount, naziv = 0.0, "Partner"
                for off in search_range:
                    if 0 <= i + off < len(lines):
                        s_line = lines[i+off]
                        ams = amt_pat.findall(s_line)
                        for am in ams:
                            val = float(am.replace('.', '').replace(',', '.'))
                            if val > 1.0 and amount == 0.0: amount = val
                        if naziv == "Partner" and len(s_line) > 3 and not any(c.isdigit() for c in s_line):
                            naziv = s_line
                
                if amount > 0:
                    data.append({
                        "Datum": glavni_datum, "Konto": "2221", "Naziv": naziv[:35],
                        "IBAN": iban, "Duguje": "{:.2f}".format(amount).replace('.', ','), "Potražuje": "0,00"
                    })

        if data:
            st.table(data)
            hub3_res = generate_hub3(data)
            st.download_button("⬇️ Preuzmi HUB3", hub3_res, f"izvod_{banka.lower()}.hub3")
        else:
            st.warning("Nije pronađeno ništa.")
    except Exception as e:
        st.error(f"Greška: {e}")
