import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. POSTAVKE STRANICE I DIZAJN
st.set_page_config(page_title="Lucced PDF Konverter", page_icon="🏦", layout="centered")

# CSS za hover animacije na polju za upload i gumbima
st.markdown("""
    <style>
    /* Animacija polja za upload */
    [data-testid="stFileUploader"] {
        transition: all 0.4s ease-in-out;
        border: 2px dashed #4e73df;
        border-radius: 15px;
        padding: 10px;
    }
    [data-testid="stFileUploader"]:hover {
        transform: scale(1.02);
        border-color: #ff4b4b;
        box-shadow: 0px 10px 25px rgba(0,0,0,0.15);
    }
    /* Stil tablice */
    .stTable {
        background-color: #f8f9fc;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📄 PDF file u XML, HUB3 file")
st.write("Učitajte RBA izvadak za automatsko knjiženje u Lucced tablicu.")

# 2. FUNKCIJA ZA GENERIRANJE XML-a (SVI PODACI)
def generate_lucced_xml(transactions):
    root = ET.Element("Document", {"xmlns": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"})
    initn = ET.SubElement(root, "CstmrCdtTrfInitn")
    
    grphdr = ET.SubElement(initn, "GrpHdr")
    ET.SubElement(grphdr, "MsgId").text = f"LUCCED-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "CreDtTm").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "NbOfTxs").text = str(len(transactions))
    
    pmt_inf = ET.SubElement(initn, "PmtInf")
    
    for tx in transactions:
        tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
        
        # Iznos
        amt = ET.SubElement(tx_inf, "Amt")
        ET.SubElement(amt, "InstdAmt", {"Ccy": "EUR"}).text = tx['Iznos']
        
        # Primatelj
        cdtr = ET.SubElement(tx_inf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = tx['Naziv_Partnera']
        
        # IBAN
        cdtr_acct = ET.SubElement(tx_inf, "CdtrAcct")
        ET.SubElement(ET.SubElement(cdtr_acct, "Id"), "IBAN").text = tx['IBAN']
        
        # Svrha i Konto (Mapiranje za Lucced)
        rmt = ET.SubElement(tx_inf, "RmtInf")
        ET.SubElement(rmt, "Ustrd").text = f"KONTO:{tx['Konto']} | {tx['Opis']} | {tx['Poziv_na_broj']}"

    output = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output.getvalue()

# 3. GLAVNA LOGIKA ZA OBRADU PDF-a
uploaded_file = st.file_uploader("Odaberite RBA izvadak (PDF)", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            lines = [l.strip() for l in full_text.split('\n') if l.strip()]

        stavke_za_tablicu = []
        
        # --- EKSTRAKCIJA GLAVNOG PLAĆANJA ---
        amount_match = re.search(r'D\s+([\d\.]+,\d{2})', full_text)
        iban_match = re.search(r'HR\d{19}', full_text.replace(" ", ""))
        
        if amount_match and iban_match:
            glavni_iznos = amount_match.group(1).replace('.', '').replace(',', '.')
            if float(glavni_iznos) > 1.0:
                clean_iban = iban_match.group(0)
                naziv, opis = "Nepoznato", "Placanje po ugovoru"
                
                for i, line in enumerate(lines):
                    if clean_iban in line.replace(" ", ""):
                        if i+1 < len(lines): naziv = lines[i+1].strip()
                        if i+3 < len(lines): opis = lines[i+3].strip()
                        break
                
                stavke_za_tablicu.append({
                    "Konto": "2221",
                    "Naziv_Partnera": naziv,
                    "Opis": opis,
                    "IBAN": clean_iban,
                    "Iznos": glavni_iznos,
                    "Poziv_na_broj": "HR99"
                })

        # --- EKSTRAKCIJA NAKNADE (Onih 0,40 sa slike) ---
        if "Naknada" in full_text:
            fee_match = re.search(r'D\s+0,40', full_text)
            if fee_match:
                stavke_za_tablicu.append({
                    "Konto": "4650",
                    "Naziv_Partnera": "RBA Banka",
                    "Opis": "Naknada - EURO NKS",
                    "IBAN": "HR0624840081000000013", # RBA IBAN za naknade
                    "Iznos": "0.40",
                    "Poziv_na_broj": "HR99"
                })

        # 4. PRIKAZ TABLICE I DOWNLOAD
        if stavke_za_tablicu:
            st.success("✅ Podaci isčitani prema Lucced strukturi:")
            st.table(stavke_za_tablicu) # Prikaz tablice kao na tvojoj slici
            
            xml_data = generate_lucced_xml(stavke_za_tablicu)
            
            st.download_button(
                label="⬇️ Preuzmi XML, HUB3 file",
                data=xml_data,
                file_name=uploaded_file.name.replace(".pdf", ".xml"),
                mime="application/xml"
            )
        else:
            st.warning("Nije pronađena niti jedna transakcija. Provjerite PDF.")

    except Exception as e:
        st.error(f"Greška pri obradi datoteke: {e}")

else:
    st.info("💡 Savjet: Samo povucite PDF datoteku iznad za početak.")

