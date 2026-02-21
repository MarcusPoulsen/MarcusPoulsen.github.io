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

	# --- AI summary block ---
	total_usage = df['usage_kwh'].sum()
	total_cost = df['total_udgift'].sum() if 'total_udgift' in df.columns else (df['usage_kwh'] * df['total_pris_per_kwh']).sum()
	avg_price = (df['total_pris_per_kwh'].mean() if 'total_pris_per_kwh' in df.columns else None)
	peak_hour = df['time'].dt.hour[df['spot_pris'].idxmax()] if 'spot_pris' in df.columns else None
	peak_price = df['spot_pris'].max() if 'spot_pris' in df.columns else None
	summary_lines = [
		f"**AI-analyse af perioden {from_date} til {to_date}:**",
		f"- Dit samlede elforbrug var **{total_usage:.0f} kWh**.",
		f"- Din samlede udgift var **{total_cost:.0f} kr.**.",
	]
	if avg_price:
		summary_lines.append(f"- Gennemsnitlig pris: **{avg_price:.2f} kr./kWh**.")
	if peak_hour is not None and peak_price is not None:
		summary_lines.append(f"- Dyreste time: **kl. {peak_hour}:00** med **{peak_price:.2f} kr./kWh**.")
	st.info("\n".join(summary_lines))
	# --- End AI summary block ---

	st.markdown("### Grafer")
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
