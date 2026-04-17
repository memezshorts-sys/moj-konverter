import streamlit as st
import pdfplumber
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io

# 1. DIZAJN STRANICE
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

st.title("📄 PDF file u XML, HUB3 file")
st.write("### HPB & RBA Automatska Obrada")

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
        # Lucced mapiranje
        ET.SubElement(rmt, "Ustrd").text = f"KONTO:{tx['Konto']} | {tx['Naziv']}"

    output = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output.getvalue()

uploaded_file = st.file_uploader("Povucite HPB PDF izvadak ovdje", type="pdf")

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
        
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        tablica_lucced = []
        ukupno_duguje = 0.0

        # --- PAMETNO PREPOZNAVANJE STAVKI (HPB SPECIFIČNO) ---
        # Tražimo uzorak IBAN-a i iznosa u blizini
        for i, line in enumerate(lines):
            # 1. Pronađi IBAN primatelja
            iban_match = re.search(r'HR\d{19}', line.replace(" ", ""))
            if iban_match:
                clean_iban = iban_match.group(0)
                
                # 2. Potraži iznos u istom ili sljedećih par redova (HPB format)
                # Tražimo broj s dva decimalna mjesta koji je u koloni "Duguje/Isplata"
                found_amount = 0.0
                for offset in range(-1, 4): # Gledamo red iznad i par redova ispod
                    if i + offset < len(lines):
                        # Regex za iznos (npr. 20,40 ili 1.234,56)
                        amt_match = re.findall(r'(\d+[\d\.]*,\d{2})', lines[i+offset])
                        for a in amt_match:
                            val = float(a.replace('.', '').replace(',', '.'))
                            # Filtriramo datume i rezervacije (HPB iznosi su obično desno)
                            if val > 1.0: 
                                found_amount = val
                                break
                
                # 3. Pronađi naziv (u HPB izvatku je često desno od IBAN-a)
                naziv = line.split(clean_iban)[-1].strip() if clean_iban in line.replace(" ","") else "Partner"
                if not naziv or len(naziv) < 3:
                    if i + 1 < len(lines): naziv = lines[i+1].split()[0] # Uzmi prvu riječ iz reda ispod

                if found_amount > 0:
                    tablica_lucced.append({
                        "Konto": "2221", "Partner": "503", "Naziv": naziv[:30], 
                        "Duguje": "{:.2f}".format(found_amount), "Potražuje": "0.00"
                    })
                    ukupno_duguje += found_amount

        # 4. DODAVANJE IZVODA (Konto 1000)
        if tablica_lucced:
            # Dodajemo redak "Izvod" koji zbraja sve transakcije
            tablica_lucced.append({
                "Konto": "1000", "Partner": "", "Naziv": "Izvod", 
                "Duguje": "0.00", "Potražuje": "{:.2f}".format(ukupno_duguje)
            })

            st.success(f"✅ Uspješno isčitano {len(tablica_lucced)-1} transakcija.")
            st.table(tablica_lucced)
            
            xml_data = generate_lucced_xml(tablica_lucced)
            st.download_button(label="⬇️ Preuzmi XML, HUB3 file", data=xml_data, file_name="hpb_izvod_lucced.xml")
            st.balloons()
        else:
            st.warning("Nije pronađena nijedna transakcija. Provjerite je li PDF tekstualni.")

    except Exception as e:
        st.error(f"Došlo je do greške: {e}")
else:
    st.info("💡 Savjet: Ovaj sustav sada prepoznaje više transakcija odjednom iz HPB izvatka.")
