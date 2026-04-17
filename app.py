import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# --- DIZAJN I STILIZACIJA ---
st.set_page_config(page_title="Panda Lucced Konverter", page_icon="🐼", layout="centered")

st.markdown("""
    <style>
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

    /* Bijeli tekst svuda */
    html, body, [class*="st-"], h1, h2, h3, p, span, label { color: #ffffff !important; }

    /* Optimiziran i prozirni Upload pravokutnik */
    [data-testid="stFileUploader"] {
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 2px dashed #00d2ff !important;
        border-radius: 20px !important;
        padding: 60px 20px !important;
        min-height: 280px !important;
        transition: all 0.4s ease-in-out;
    }
    [data-testid="stFileUploader"] section { background-color: transparent !important; }
    [data-testid="stFileUploader"] button {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border: 1px solid rgba(0, 210, 255, 0.5) !important;
    }
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
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF u HUB3 file (Lucced)")
st.write("### Optimizirana obrada za Panda knjigovodstvo")

# --- GENERIRANJE HUB3 XML-a ---
def generate_lucced_hub3(transactions):
    # Namespace specifičan za HR bankarske sustave
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    ET.register_namespace('', ns)
    
    root = ET.Element("{%s}Document" % ns)
    initn = ET.SubElement(root, "{%s}CstmrCdtTrfInitn" % ns)
    
    # Header sekcija
    grphdr = ET.SubElement(initn, "{%s}GrpHdr" % ns)
    ET.SubElement(grphdr, "{%s}MsgId" % ns).text = f"PANDA-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "{%s}CreDtTm" % ns).text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "{%s}NbOfTxs" % ns).text = str(len(transactions))
    
    # Podaci o pošiljatelju (Panda)
    initg_pty = ET.SubElement(grphdr, "{%s}InitgPty" % ns)
    ET.SubElement(initg_pty, "{%s}Nm" % ns).text = "Panda Knjigovodstvo"

    # Payment Information
    pmt_inf = ET.SubElement(initn, "{%s}PmtInf" % ns)
    ET.SubElement(pmt_inf, "{%s}PmtInfId" % ns).text = "ISPLATA-" + datetime.now().strftime('%Y%m%d')
    ET.SubElement(pmt_inf, "{%s}PmtMtd" % ns).text = "TRF"
    
    # Platitelj (Debtor)
    dbtr = ET.SubElement(pmt_inf, "{%s}Dbtr" % ns)
    ET.SubElement(dbtr, "{%s}Nm" % ns).text = "Korisnik Programa"

    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, "{%s}CdtTrfTxInf" % ns)
        p_id = ET.SubElement(tx_inf, "{%s}PmtId" % ns)
        ET.SubElement(p_id, "{%s}EndToEndId" % ns).text = "HR99"
        
        # Iznos (formatiran na .2f)
        amt = ET.SubElement(tx_inf, "{%s}Amt" % ns)
        val = tx['Duguje'] if tx['Duguje'] != "0.00" else tx['Potražuje']
        ET.SubElement(amt, "{%s}InstdAmt" % ns, {"Ccy": "EUR"}).text = str(val)
        
        # Primatelj
        cdtr = ET.SubElement(tx_inf, "{%s}Cdtr" % ns)
        ET.SubElement(cdtr, "{%s}Nm" % ns).text = tx['Naziv'][:70]
        
        # Svrha (Lucced mapiranje konta)
        rmt = ET.SubElement(tx_inf, "{%s}RmtInf" % ns)
        ET.SubElement(rmt, "{%s}Ustrd" % ns).text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"

    output = io.BytesIO()
    output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=False)
    return output.getvalue()

# --- INPUT OBRADA ---
uploaded_file = st.file_uploader("Povucite PDF ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        tablica = []
        ukupno = 0.0

        # Pametno traženje transakcija
        for i, line in enumerate(lines):
            iban_match = re.search(r'HR\d{19}', line.replace(" ", ""))
            if iban_match:
                iban = iban_match.group(0)
                amount = 0.0
                # Gledamo okolicu IBAN-a za iznos
                for off in range(-1, 4):
                    if i+off < len(lines):
                        match = re.findall(r'(\d+[\d\.]*,\d{2})', lines[i+off])
                        for m in match:
                            v = float(m.replace('.', '').replace(',', '.'))
                            if v > 1.0: amount = v; break
                
                naziv = line.split(iban)[-1].strip() if iban in line.replace(" ","") else "Partner"
                if amount > 0:
                    tablica.append({"Konto": "2221", "Naziv": naziv[:35], "Duguje": "{:.2f}".format(amount), "Potražuje": "0.00"})
                    ukupno += amount

        # Zatvaranje izvoda (Konto 1000)
        if tablica:
            if "0,40" in full_text: # Naknada
                tablica.append({"Konto": "4650", "Naziv": "Bankovna naknada", "Duguje": "0.40", "Potražuje": "0.00"})
                ukupno += 0.40
            
            tablica.append({"Konto": "1000", "Naziv": "Izvod", "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno)})
            
            st.table(tablica)
            hub3_data = generate_lucced_hub3(tablica)
            
            st.download_button(
                label="⬇️ Preuzmi .hub3 datoteku",
                data=hub3_data,
                file_name=f"izvod_{datetime.now().strftime('%H%M%S')}.hub3",
                mime="application/octet-stream"
            )
    except Exception as e:
        st.error(f"Greška: {e}")
