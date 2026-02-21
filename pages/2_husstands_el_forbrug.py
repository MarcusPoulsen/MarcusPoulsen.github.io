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


	# --- OpenAI summary block ---
	import openai
	import os
	openai_api_key = st.secrets["openai_api_key"] if "openai_api_key" in st.secrets else os.getenv("OPENAI_API_KEY")
	total_usage = df['usage_kwh'].sum()
	total_cost = df['total_udgift'].sum() if 'total_udgift' in df.columns else (df['usage_kwh'] * df['total_pris_per_kwh']).sum()
	avg_price = (df['total_pris_per_kwh'].mean() if 'total_pris_per_kwh' in df.columns else None)
	peak_hour = df['time'].dt.hour[df['spot_pris'].idxmax()] if 'spot_pris' in df.columns else None
	peak_price = df['spot_pris'].max() if 'spot_pris' in df.columns else None
	prompt = f"""
	Du er en hjælpsom energirådgiver. Brug tallene nedenfor til at skrive en kort, brugervenlig opsummering og evt. et råd til brugeren:
	Periode: {from_date} til {to_date}
	Samlet elforbrug: {total_usage:.0f} kWh
	Samlet udgift: {total_cost:.0f} kr.
	Gennemsnitlig pris: {avg_price:.2f} kr./kWh
	Dyreste time: kl. {peak_hour}:00 med {peak_price:.2f} kr./kWh
	"""
	ai_message = None
	if openai_api_key:
		try:
			client = openai.OpenAI(api_key=openai_api_key)
			response = client.chat.completions.create(
				model="gpt-3.5-turbo",
				messages=[{"role": "system", "content": "Du er en hjælpsom energirådgiver."},
						  {"role": "user", "content": prompt}],
				max_tokens=120,
				temperature=0.6
			)
			ai_message = response.choices[0].message.content.strip()
		except Exception as e:
			ai_message = f"Kunne ikke hente AI-besked: {e}"
	else:
		ai_message = "Ingen OpenAI API-nøgle fundet. Tilføj den som 'openai_api_key' i Streamlit secrets eller som miljøvariabel 'OPENAI_API_KEY'."
	st.info(ai_message)
	# --- End OpenAI summary block ---

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
