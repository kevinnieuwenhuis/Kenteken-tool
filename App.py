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
    page_bg = """
    <style>
    .stApp {
        background-color: white;
    }

    label, h1, h2, h3, h4, h5, h6,
    .stButton > button, .stDownloadButton > button {
        color: black !important;
    }

    .stTextInput input,
    .stSelectbox div[data-baseweb="select"] div,
    .stNumberInput input {
        color: black !important;
        background-color: white !important;
        border: 1px solid #999 !important;
    }

    ::placeholder {
        color: #666 !important;
        opacity: 1 !important;
    }

    .stAlert div {
        color: white !important;
    }
    </style>
    """
    st.markdown(page_bg, unsafe_allow_html=True)

