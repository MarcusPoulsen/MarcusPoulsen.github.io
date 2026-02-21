import streamlit as st
import numpy as np

st.markdown("## Clever-abonnement beregner")



# Input columns: 1st row c1, c2, c3, c4; 2nd row c1, c2, c3
row1 = st.columns(4)
row2 = st.columns(3)

km_per_year = row1[0].number_input("Km om året", min_value=0, value=20000, step=100)
consumption_per_100km = row1[1].number_input("Elbil forbrug (kWh/100 km)", min_value=0.0, value=20.0, step=0.1)
ladetab_pct = row1[2].number_input("Antaget ladetab (%)", min_value=0.0, max_value=100.0, value=8.0, step=0.1)
hjemme_pct = row1[3].number_input("Hjemmeopladning procent (%)", min_value=0.0, max_value=100.0, value=90.0, step=0.1)

ude_pris_kwh = row2[0].number_input("Udeladning pris pr kWh (DKK)", min_value=0.0, value=2.5, step=0.01)
hjemme_pris_kwh = row2[1].number_input("Hjemmeladning pris pr kWh (DKK)", min_value=0.0, value=1.0, step=0.01)
saeson_effekt = row2[2].radio("Sæson effekt medregnes?", ["ja", "nej"], index=0)

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

monthly_cost_home = monthly_kwh_home * hjemme_pris_kwh
monthly_cost_ude = monthly_kwh_ude * ude_pris_kwh
total_cost = monthly_cost_home.sum() + monthly_cost_ude.sum()

# Table output
import pandas as pd
result_df = pd.DataFrame({
	"Måned": month_names,
	"Km": np.round(np.full(months, km_per_month), 0),
	"Opladningsbehov i alt (kWh)": np.round(monthly_kwh_charged, 1),
	"Hjemmeopladning (kWh)": np.round(monthly_kwh_home, 1),
	"Udeopladning (kWh)": np.round(monthly_kwh_ude, 1),
	"Hjemmeopladningsudgift (DKK)": np.round(monthly_cost_home, 0),
	"Udeopladningsudgift (DKK)": np.round(monthly_cost_ude, 0),
	"total udgift (DKK)": np.round(monthly_cost_home + monthly_cost_ude, 0)
})

st.markdown("### Resultat – månedlig oversigt")
st.dataframe(result_df, width='stretch')
st.markdown(f"**Total årlig udgift:** <b>{total_cost:.0f} DKK</b>", unsafe_allow_html=True)
