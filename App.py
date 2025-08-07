import streamlit as st
import requests
from datetime import datetime
from pathlib import Path
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import base64

# RDW API endpoint
RDW_API_URL = "https://opendata.rdw.nl/resource/m9d7-ebf2.json"

def get_vehicle_data(kenteken):
    params = {"kenteken": kenteken.replace("-", "").upper()}
    response = requests.get(RDW_API_URL, params=params)
    if response.status_code == 200 and response.json():
        return response.json()[0]
    return None

def calculate_bijtelling(cataloguswaarde, dga_of_ib, bouwjaar, jaar, datum_tenaamstelling, youngtimer_waarde=None):
    huidige_jaar = int(jaar)
    leeftijd_auto = huidige_jaar - bouwjaar

    if leeftijd_auto >= 15:
        if youngtimer_waarde and youngtimer_waarde > 0:
            bijtelling_percentage = 0.35
            bijtelling_basis = youngtimer_waarde
        else:
            return None, "Geen economische waarde ingevoerd voor youngtimer. Bijtelling kan niet worden berekend."
    else:
        if cataloguswaarde is None or cataloguswaarde == 0:
            return None, "Geen cataloguswaarde bekend. Bijtelling kan niet worden berekend voor niet-youngtimers."
        bijtelling_percentage = 0.22
        bijtelling_basis = cataloguswaarde

    if datum_tenaamstelling and isinstance(datum_tenaamstelling, str) and len(datum_tenaamstelling) >= 8 and datum_tenaamstelling[:4] == jaar:
        maand_tenaamstelling = int(datum_tenaamstelling[4:6])
        maanden_gebruikt = 12 - maand_tenaamstelling + 1
    else:
        maanden_gebruikt = 12

    bijtelling = (bijtelling_basis * bijtelling_percentage) * (maanden_gebruikt / 12)
    return bijtelling, f"Berekening: {bijtelling_basis} * {bijtelling_percentage*100:.1f}% * {maanden_gebruikt}/12"

def calculate_btw_correction(cataloguswaarde, is_btw_auto, datum_tenaamstelling, jaar):
    if not cataloguswaarde or cataloguswaarde == 0:
        return None, "Geen cataloguswaarde bekend. BTW-correctie kan niet worden berekend."

    if datum_tenaamstelling and isinstance(datum_tenaamstelling, str) and len(datum_tenaamstelling) >= 8:
        jaar_tenaamstelling = int(datum_tenaamstelling[:4])
    else:
        return None, "Geen datum laatste tenaamstelling gevonden. Kan BTW-correctie niet berekenen."

    gebruiksjaren = int(jaar) - jaar_tenaamstelling

    if not is_btw_auto or gebruiksjaren >= 5:
        return cataloguswaarde * 0.015, "1,5% over cataloguswaarde (marge auto of > 5 jaar in gebruik)"
    return cataloguswaarde * 0.027, "2,7% over cataloguswaarde (btw-auto < 5 jaar in gebruik)"

def generate_pdf(kenteken, bouwjaar, datum_tenaamstelling, cataloguswaarde, bijtelling, berekening_info, btw_correctie, btw_info):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    logo_path = Path(__file__).parent / "iqount_logo.jpg"
    logo = ImageReader(logo_path)
    c.drawImage(logo, 0, 0, width=width, height=height, mask='auto')

    c.setFont("Helvetica", 12)
    c.setFillColorRGB(0, 0, 0)

    c.drawString(50, 800, "Kenteken & Bijtelling Rapport")
    c.drawString(50, 770, f"Kenteken: {kenteken}")
    c.drawString(50, 750, f"Bouwjaar: {bouwjaar}")
    c.drawString(50, 730, f"Datum laatste tenaamstelling: {datum_tenaamstelling or 'Onbekend'}")
    c.drawString(50, 710, f"Cataloguswaarde: € {cataloguswaarde if cataloguswaarde else 'Onbekend'}")
    if bijtelling is not None:
        c.drawString(50, 680, f"Bijtelling: € {bijtelling:,.2f}")
        c.drawString(50, 660, berekening_info)
    else:
        c.drawString(50, 680, "Bijtelling: Kan niet berekend worden")

    if btw_correctie is not None:
        c.drawString(50, 630, f"BTW-correctie: € {btw_correctie:,.2f}")
        c.drawString(50, 610, btw_info)
    else:
        c.drawString(50, 630, "BTW-correctie: Kan niet berekend worden")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def add_background(logo_path):
    with open(logo_path, "rb") as image_file:
        encoded_logo = base64.b64encode(image_file.read()).decode()

    page_bg = f"""
    <style>
    .stApp {{
        background-image: linear-gradient(rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0.7)),
                          url("data:image/jpg;base64,{encoded_logo}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}
    html, body, [class*="st-"], .stApp *, div, span, label, input, select, textarea {{
        color: black !important;
    }}
    ::placeholder {{
        color: #333 !important;
        opacity: 1 !important;
    }}
    .stRadio > label, .stSelectbox > label, .stTextInput > label, .stNumberInput > label {{
        color: black !important;
    }}
    .css-1cpxqw2, .css-1fv8s86 {{
        color: black !important;
    }}
    .stButton>button, .stDownloadButton>button {{
        color: black !important;
        background-color: #e0e0e0 !important;
        border: 1px solid #555 !important;
    }}
    h1, h2, h3, h4, h5, h6 {{
        color: black !important;
    }}
    .stAlert div {{
        color: white !important;
    }}
    </style>
    """
    st.markdown(page_bg, unsafe_allow_html=True)

st.set_page_config(page_title="Kenteken & Bijtelling Tool", page_icon="🚗")
logo_path = Path(__file__).parent / "iqount_logo.jpg"
add_background(logo_path)

st.title("🚗 Kenteken & Bijtelling Tool")

kenteken = st.text_input("Voer een kenteken in (bv. AB-123-C)")
jaar = st.selectbox("Kies het jaar voor de berekening", [str(y) for y in range(datetime.now().year, datetime.now().year - 10, -1)])

if kenteken:
    data = get_vehicle_data(kenteken)
    if data:
        bouwjaar = int(data.get("datum_eerste_toelating", "00000000")[:4])
        datum_tenaamstelling = data.get("datum_tenaamstelling", "")
        cataloguswaarde = float(data.get("catalogusprijs", 0)) if data.get("catalogusprijs") else None

        st.write(f"**Bouwjaar:** {bouwjaar}")
        st.write(f"**Datum laatste tenaamstelling:** {datum_tenaamstelling or 'Onbekend'}")
        st.write(f"**Cataloguswaarde:** € {cataloguswaarde if cataloguswaarde else 'Onbekend'}")

        dga_of_ib = st.radio("Kies type ondernemer:", ["DGA", "IB-ondernemer"])
        is_btw_auto = st.radio("Is dit een BTW-auto?", ["Ja", "Nee"]) == "Ja"

        leeftijd_auto = int(jaar) - bouwjaar
        youngtimer_waarde = None
        if leeftijd_auto >= 15:
            youngtimer_waarde = st.number_input("Economische waarde (Youngtimer)", min_value=0.0, step=100.0)

        if st.button("Bereken"):
            bijtelling, berekening_info = calculate_bijtelling(cataloguswaarde, dga_of_ib, bouwjaar, jaar, datum_tenaamstelling, youngtimer_waarde)
            btw_correctie, btw_info = calculate_btw_correction(cataloguswaarde, is_btw_auto, datum_tenaamstelling, jaar)

            if bijtelling:
                st.success(f"Bijtelling: € {bijtelling:,.2f}")
                st.caption(berekening_info)
            else:
                st.warning(berekening_info)

            if btw_correctie is not None:
                st.info(f"BTW-correctie privégebruik: € {btw_correctie:,.2f}")
                st.caption(btw_info)
            else:
                st.warning(btw_info)

            pdf_buffer = generate_pdf(kenteken, bouwjaar, datum_tenaamstelling, cataloguswaarde, bijtelling, berekening_info, btw_correctie, btw_info)
            st.download_button("Download rapport als PDF", data=pdf_buffer, file_name=f"bijtelling_{kenteken}.pdf", mime="application/pdf")
    else:
        st.error("Geen voertuig gevonden voor dit kenteken.")

