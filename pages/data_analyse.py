import streamlit as st

st.set_page_config(page_title="Data Analyse", layout="wide")

st.title("Data Analyse")

# Import tab modules
from tabs.daily_summary_tab import render as render_daily_summary_tab
from tabs.car_charge_tab import render as render_car_charge_tab
from tabs.data_table_tab import render as render_data_table_tab
from tabs.hourly_stats_tab import render as render_hourly_stats_tab
from tabs.charts_tab import render as render_charts_tab

import pandas as pd

st.markdown("""
<style>
.stPageLinkButton {
	background-color: #0099ff !important;
	color: white !important;
	font-size: 1.1em !important;
	padding: 0.5em 1.2em !important;
	border-radius: 6px !important;
	margin-bottom: 1em !important;
	border: none !important;
}
</style>
""", unsafe_allow_html=True)
st.page_link("app.py", label="Til Forside", icon="🏠", key="forside_link")

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
	udeladning_pris = st.session_state.get('udeladning_pris', 3.5)

	st.markdown("### Clever refusion vs pris på opladning")
	render_car_charge_tab(df, from_date, to_date, _filter_df_by_view_range, udeladning_pris)
	st.divider()
	st.markdown("### Data Deep dive")
	render_data_table_tab(df, from_date, to_date, _filter_df_by_view_range)
	st.divider()
	st.markdown("### Daily Summary")
	render_daily_summary_tab(df, from_date, to_date, _filter_df_by_view_range)
	st.divider()
	st.markdown("### Hourly Stats")
	render_hourly_stats_tab(df, from_date, to_date, _filter_df_by_view_range)
	st.divider()
	st.markdown("### Charts")
	render_charts_tab(df, from_date, to_date, _filter_df_by_view_range)
else:
	st.warning("Ingen data fundet. Gå til forsiden og hent data først.")
