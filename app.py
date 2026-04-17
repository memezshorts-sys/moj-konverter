import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# Podešavanje stranice
st.set_page_config(page_title="RBA u XML Konverter", page_icon="🏦")

st.title("🏦 RBA Izvadak u HUB3 XML")
st.write("Učitajte PDF izvadak i preuzmite datoteku za Lucced bez ikakve instalacije.")

def generate_xml(data):
    """Generira ISO 20022 XML (pain.001) format."""
    root = ET.Element("Document", {"xmlns": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"})
    initn = ET.SubElement(root, "CstmrCdtTrfInitn")
    
    grphdr = ET.SubElement(initn, "GrpHdr")
    ET.SubElement(grphdr, "MsgId").text = f"LUCCED-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(grphdr, "CreDtTm").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grphdr, "NbOfTxs").text = "1"
    
    pmt_inf = ET.SubElement(initn, "PmtInf")
    tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
    
    amt = ET.SubElement(tx_inf, "Amt")
    ET.SubElement(amt, "InstdAmt", {"Ccy": "EUR"}).text = data['amount']
    
    cdtr = ET.SubElement(tx_inf, "Cdtr")
    ET.SubElement(cdtr, "Nm").text = data['recipient']
    
    cdtr_acct = ET.SubElement(tx_inf, "CdtrAcct")
    ET.SubElement(ET.SubElement(cdtr_acct, "Id"), "IBAN").text = data['iban']
    
    rmt = ET.SubElement(tx_inf, "RmtInf")
    ET.SubElement(rmt, "Ustrd").text = f"{data['purpose']} HR99"

    output = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output.getvalue()

# Web sučelje
uploaded_file = st.file_uploader("Povucite RBA PDF ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            
        # RBA Logika za izvlačenje podataka
        amount_match = re.search(r'D\s+([\d\.]+,\d{2})', full_text)
        iban_match = re.search(r'HR\d{19}', full_text.replace(" ", ""))
        
        if amount_match and iban_match:
            amt = amount_match.group(1).replace('.', '').replace(',', '.')
            if float(amt) > 1.0: # Preskače naknade
                iban = iban_match.group(0)
                
                # Traženje primatelja i svrhe (redovi ispod IBAN-a)
                lines = full_text.split('\n')
                recipient, purpose = "Nepoznato", "Placanje"
                for i, line in enumerate(lines):
                    if iban in line.replace(" ", ""):
                        if i+1 < len(lines): recipient = lines[i+1].strip()
                        if i+3 < len(lines): purpose = lines[i+3].strip()
                        break
                
                # Prikaz rezultata na stranici
                st.success("✅ Podaci uspješno isčitani!")
                st.write(f"**Primatelj:** {recipient}")
                st.write(f"**Iznos:** {amt} EUR")
                st.write(f"**IBAN:** {iban}")
                
                xml_data = generate_xml({"amount": amt, "iban": iban, "recipient": recipient, "purpose": purpose})
                
                # Gumb za preuzimanje (Download)
                st.download_button(
                    label="⬇️ Preuzmi XML datoteku",
                    data=xml_data,
                    file_name=uploaded_file.name.replace(".pdf", ".xml"),
                    mime="application/xml"
                )
        else:
            st.warning("Nije pronađena transakcija. Provjerite je li ovo ispravan RBA izvadak.")
            
    except Exception as e:
        st.error(f"Došlo je do greške: {e}")
