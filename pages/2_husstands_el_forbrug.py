import streamlit as st

st.set_page_config(page_title="Hustands elforbrug og priser", layout="wide")

# Import tab modules
from tabs.daily_summary_tab import render as render_daily_summary_tab
from tabs.data_table_tab import render as render_data_table_tab
from tabs.hourly_stats_tab import render as render_hourly_stats_tab
from tabs.charts_tab import render as render_charts_tab

import pandas as pd

st.page_link("app.py", label="Til Forside", icon="⚡️")
st.page_link("pages/1_elbil_opladning.py", label="Gå til elbil opladning analyse", icon="🚗")


def _filter_df_by_view_range(df, view_range):
	try:
		if isinstance(view_range, tuple) and len(view_range) == 2:
			vf_from, vf_to = view_range
		else:
			vf_from = view_range
			vf_to = view_range
		if vf_from is None and vf_to is None:
			return df
		if vf_from is not None and not isinstance(vf_from, pd.Timestamp):
			vf_from = pd.to_datetime(vf_from)
		if vf_to is not None and not isinstance(vf_to, pd.Timestamp):
			vf_to = pd.to_datetime(vf_to)
		if vf_from is None:
			vf_from = df['time'].min()
		if vf_to is None:
			vf_to = df['time'].max()
		if vf_from > vf_to:
			vf_from, vf_to = vf_to, vf_from
		return df[(df['time'] >= vf_from) & (df['time'] <= vf_to)].copy()
	except Exception:
		return df

if 'df_data' in st.session_state and not st.session_state['df_data'].empty:
	df = st.session_state['df_data']
	from_date = df['time'].dt.date.min()
	to_date = df['time'].dt.date.max()


	# --- Rule-based summary block ---
	total_usage = df['usage_kwh'].sum()
	total_cost = df['total_udgift'].sum() if 'total_udgift' in df.columns else (df['usage_kwh'] * df['total_pris_per_kwh']).sum()
	avg_price = (df['total_pris_per_kwh'].mean() if 'total_pris_per_kwh' in df.columns else None)
	peak_price = df['spot_pris'].max() if 'spot_pris' in df.columns else None
	# Calculate period in months
	n_months = max(1, ((to_date.year - from_date.year) * 12 + (to_date.month - from_date.month) + 1))
	# Monthly averages
	monthly_usage = total_usage / n_months
	# Car and house usage/costs
	car_kwh = df['car_kwh'].sum() if 'car_kwh' in df.columns else 0.0
	house_kwh = df['house_kwh'].sum() if 'house_kwh' in df.columns else (total_usage - car_kwh)
	car_cost = (df['car_kwh'] * df['total_pris_per_kwh']).sum() if 'car_kwh' in df.columns else 0.0
	house_cost = (df['house_kwh'] * df['total_pris_per_kwh']).sum() if 'house_kwh' in df.columns else (total_cost - car_cost)
	avg_house_price = (house_cost / house_kwh) if house_kwh > 0 else 0.0
	avg_car_price = (car_cost / car_kwh) if car_kwh > 0 else 0.0
	monthly_car_kwh = car_kwh / n_months
	# Main summary
	summary = f"**Periode:** {from_date} til {to_date}\n"
	summary += f"- Samlet elforbrug: **{total_usage:.0f} kWh**\n"
	summary += f"- Samlet udgift: **{total_cost:.0f} kr.**\n"
	if avg_price:
		summary += f"- Gennemsnitlig pris: **{avg_price:.2f} kr./kWh**\n"
	# Describe user's data
	summary += f"\nDin hustand bruger i gns **{monthly_usage:.1f} kWh** pr måned, heraf bruger bilen i gennemsnit **{monthly_car_kwh:.1f} kWh** pr måned og huset **{house_kwh / n_months:.1f} kWh** pr måned.\n"
	summary += f"Dit forbrug til huset koster i gns **{avg_house_price:.2f} kr pr kWh**, og dit forbrug til bilen koster i gns **{avg_car_price:.2f} kr pr kWh**.\n"
	# Simple advice based on thresholds
	if avg_price and avg_price > 2.0:
		summary += "💡 Prisen har været høj. Overvej at flytte forbrug til billigere timer, hvis muligt.\n"
	elif avg_price and avg_price < 1.5:
		summary += "✅ Du har haft en lav gennemsnitspris. Godt gået!\n"
	st.info(summary)
	# --- End rule-based summary block ---

	st.markdown("### Månedlige omkostninger og spotpris tendenser")
	render_charts_tab(df, from_date, to_date, _filter_df_by_view_range)
	st.divider()
	st.markdown("### Data Deep dive")
	render_data_table_tab(df, from_date, to_date, _filter_df_by_view_range)
	st.divider()
	st.markdown("### Daily Summary")
	render_daily_summary_tab(df, from_date, to_date, _filter_df_by_view_range)
	st.divider()
	st.markdown("### Hourly Stats")
	render_hourly_stats_tab(df, from_date, to_date, _filter_df_by_view_range)
else:
	st.warning("Ingen data fundet. Gå til forsiden og hent data først.")
