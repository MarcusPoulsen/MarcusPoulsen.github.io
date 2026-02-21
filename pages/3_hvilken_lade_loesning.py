import streamlit as st
import numpy as np

st.markdown("## Clever-abonnement beregner")

# User inputs
km_per_year = st.number_input("Km om året", min_value=0, value=20000, step=100)
consumption_per_100km = st.number_input("Elbil forbrug (kWh/100 km)", min_value=0.0, value=20.0, step=0.1)
ladetab_pct = st.number_input("Antaget ladetab (%)", min_value=0.0, max_value=100.0, value=8.0, step=0.1)
hjemme_pct = st.number_input("Hjemmeopladning procent (%)", min_value=0.0, max_value=100.0, value=90.0, step=0.1)
saeson_effekt = st.radio("Sæson effekt medregnes?", ["ja", "nej"], index=0)

# Calculation
months = 12
km_per_month = km_per_year / months
base_kwh_per_month = km_per_month * (consumption_per_100km / 100)

# Sæson effekt: 15% ekstra forbrug i vintermåneder (nov, dec, jan, feb, mar)
saeson_factor = np.ones(months)
if saeson_effekt == "ja":
	saeson_factor[[10,11,0,1,2]] = 1.15  # Nov, Dec, Jan, Feb, Mar

monthly_kwh = base_kwh_per_month * saeson_factor

# Ladetab: skal lade mere end du bruger
monthly_kwh_charged = monthly_kwh * (1 + ladetab_pct / 100)

# Hjemmeopladning
monthly_kwh_home = monthly_kwh_charged * (hjemme_pct / 100)
monthly_kwh_ude = monthly_kwh_charged * (1 - hjemme_pct / 100)


# Separate prices for home and away charging
hjemme_pris_kwh = st.number_input("Hjemmeladning pris pr kWh (DKK)", min_value=0.0, value=1.0, step=0.01)
ude_pris_kwh = st.number_input("Udeladning pris pr kWh (DKK)", min_value=0.0, value=2.5, step=0.01)

monthly_cost_home = monthly_kwh_home * hjemme_pris_kwh
monthly_cost_ude = monthly_kwh_ude * ude_pris_kwh
total_cost = monthly_cost_home.sum() + monthly_cost_ude.sum()

st.markdown("### Resultat")
st.write(f"Antal km pr måned: {km_per_month:.0f}")
st.write(f"Forventet kWh forbrug pr måned (uden ladetab/sæson): {base_kwh_per_month:.1f}")
st.write(f"Forventet kWh forbrug pr måned (inkl. ladetab/sæson): {monthly_kwh_charged.round(1)}")
st.write(f"Hjemmeopladning pr måned (kWh): {monthly_kwh_home.round(1)}")
st.write(f"Udeopladning pr måned (kWh): {monthly_kwh_ude.round(1)}")
st.write(f"Hjemmeopladningsudgift pr måned (DKK): {monthly_cost_home.round(0)}")
st.write(f"Udeopladningsudgift pr måned (DKK): {monthly_cost_ude.round(0)}")
st.write(f"Total årlig udgift: {total_cost:.0f} DKK")
