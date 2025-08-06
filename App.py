import streamlit as st
import requests
from datetime import datetime
from pathlib import Path
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# RDW API endpoint
RDW_API_URL = "https://opendata.rdw.nl/resource/m9d7-ebf2.json"

def get_vehicle_data(kenteken):
    params = {"kenteken": kenteken.replace("-", "").upper()}
    response = requests.get(RDW_API_URL, params=params)
    if response.status_code == 200 and response.json():
        return response.json()[0]  # Eerste resultaat
    return None

def calculate_bijtelling(cataloguswaarde, dga_of_ib, bouwjaar, jaar, datum_tenaamstelling, youngtimer_waarde=None):
    huidige_jaar = int(jaar)
    leeftijd_auto = huidige_jaar - bouwjaar

    # Youngtimer check
    if leeftijd_auto >= 15:
        if youngtimer_waarde:
            bijtelling_percentage = 0.35
            bijtelling_basis = youngtimer_waarde
        else:
            return None, "Youngtimer waarde ontbreekt"
    else:
        bijtelling_percentage = 0.22
        bijtelling_basis = cataloguswaarde

    # Gedeeltelijke bijtelling
    if datum_tenaamstelling and datum_tenaamstelling[:4] == jaar:
        maand_tenaamstelling = int(datum_tenaamstelling[4:6])
        maanden_gebruikt = 12 - maand_tenaamstelling + 1
    else:
        maanden_gebruikt = 12

    bijtelling = (bijtelling_basis * bijtelling_percentage) * (maanden_gebruikt / 12)
    return bijtelling, f"Berekening: {bijtelling_basis} * {bijtelling_percentage*100:.1f}% * {maanden_gebruikt}/12"

def calculate_btw_correction(cataloguswaarde, is_btw_auto, datum_tenaamstelling, jaar):
    # Controleer of de datum tenaamstelling correct is
    if datum_tenaamstelling and len(datum_tenaamstelling) >= 8:
        jaar_tenaamstelling = int(datum_tenaamstelling[:4])
    else:
        jaar_tenaamstelling = int(jaar)  # fallback als data ontbreekt

    gebruiksjaren = int(jaar) - jaar_tenaamstelling

    # Bepalen percentage
    if not is_btw_auto or gebruiksjaren >= 5:
        return cataloguswaarde * 0.015, "1,5% over cataloguswaarde (marge auto of > 5 jaar in gebruik)"
    return cataloguswaarde * 0.027, "2,7% over cataloguswaarde (btw-auto < 5 jaar in gebruik)"


def generate_pdf(kenteken, bouwjaar, datum_tenaamstelling, cataloguswaarde, bijtelling, berekening_info, btw_correctie, btw_info):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica", 12)

    c.drawString(50, 800, "Kenteken & Bijtelling Rapport")
    c.drawString(50, 770, f"Kenteken: {kenteken}")
    c.drawString(50, 750, f"Bouwjaar: {bouwjaar}")
    c.drawString(50, 730, f"Datum laatste tenaamstelling: {datum_tenaamstelling}")
    c.drawString(50, 710, f"Cataloguswaarde: € {cataloguswaarde:,.2f}")
    c.drawString(50, 680, f"Bijtelling: € {bijtelling:,.2f}")
    c.drawString(50, 660, berekening_info)
    c.drawString(50, 630, f"BTW-correctie: € {btw_correctie:,.2f}")
    c.drawString(50, 610, btw_info)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# UI
st.set_page_config(page_title="Kenteken & Bijtelling Tool", page_icon="🚗")

# Logo tonen
logo_path = Path(__file__).parent / "iqount_logo.jpg"
st.image(str(logo_path), width=200)

st.title("🚗 Kenteken & Bijtelling Tool")

kenteken = st.text_input("Voer een kenteken in (bv. AB-123-C)")
jaar = st.selectbox("Kies het jaar voor de berekening", [str(y) for y in range(datetime.now().year, datetime.now().year - 10, -1)])

if kenteken:
    data = get_vehicle_data(kenteken)

    if data:
        bouwjaar = int(data.get("datum_eerste_toelating", "00000000")[:4])
        datum_tenaamstelling = data.get("datum_tenaamstelling", "")
        cataloguswaarde = float(data.get("catalogusprijs", 0))

        st.write(f"**Bouwjaar:** {bouwjaar}")
        st.write(f"**Datum laatste tenaamstelling:** {datum_tenaamstelling}")
        st.write(f"**Cataloguswaarde:** € {cataloguswaarde:,.2f}")

        dga_of_ib = st.radio("Kies type ondernemer:", ["DGA", "IB-ondernemer"])
        is_btw_auto = st.radio("Is dit een BTW-auto?", ["Ja", "Nee"]) == "Ja"

        leeftijd_auto = int(jaar) - bouwjaar
        youngtimer_waarde = None
        if leeftijd_auto >= 15:
            youngtimer_waarde = st.number_input("Economische waarde (Youngtimer)", min_value=0.0, step=100.0)

        if st.button("Bereken"):
            bijtelling, berekening_info = calculate_bijtelling(cataloguswaarde, dga_of_ib, bouwjaar, jaar, datum_tenaamstelling, youngtimer_waarde)
            btw_correctie, btw_info = calculate_btw_correction(cataloguswaarde, is_btw_auto, bouwjaar, jaar)

            if bijtelling:
                st.success(f"Bijtelling: € {bijtelling:,.2f}")
                st.caption(berekening_info)
                st.info(f"BTW-correctie privégebruik: € {btw_correctie:,.2f}")
                st.caption(btw_info)

                pdf_buffer = generate_pdf(kenteken, bouwjaar, datum_tenaamstelling, cataloguswaarde, bijtelling, berekening_info, btw_correctie, btw_info)
                st.download_button("Download rapport als PDF", data=pdf_buffer, file_name=f"bijtelling_{kenteken}.pdf", mime="application/pdf")
            else:
                st.error("Kan bijtelling niet berekenen. Controleer of de youngtimer-waarde is ingevuld.")
    else:
        st.error("Geen voertuig gevonden voor dit kenteken.")
