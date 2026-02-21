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


# Calculation
months = 12
month_names = ["Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
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

# Table output
import pandas as pd
result_df = pd.DataFrame({
	"Måned": month_names,
	"Km": np.round(np.full(months, km_per_month), 0),
	"KWh (uden ladetab/sæson)": np.round(np.full(months, base_kwh_per_month), 1),
	"KWh (inkl. ladetab/sæson)": np.round(monthly_kwh_charged, 1),
	"Hjemmeopladning (kWh)": np.round(monthly_kwh_home, 1),
	"Udeopladning (kWh)": np.round(monthly_kwh_ude, 1),
	"Hjemmeopladningsudgift (DKK)": np.round(monthly_cost_home, 0),
	"Udeopladningsudgift (DKK)": np.round(monthly_cost_ude, 0)
})

st.markdown("### Resultat – månedlig oversigt")
st.dataframe(result_df, width='stretch')
st.markdown(f"**Total årlig udgift:** <b>{total_cost:.0f} DKK</b>", unsafe_allow_html=True)
