import streamlit as st

st.set_page_config(page_title="Dataanalyse", layout="wide")

st.title("Opladning af elbil, forbrug og udgifter – fokuseret på Clever-kunder")
st.info('Denne side viser, hvor meget du selv betaler for din strøm, sammenlignet med den refusion, Clever udbetaler. Bemærk: Du får det mest præcise estimat, hvis du indtaster dit faktiske forbrug fra Clever-appen i felterne nedenfor.')
# Import tab modules
from tabs.car_charge_tab import render as render_car_charge_tab


import pandas as pd

st.page_link("app.py", label="Til forsiden", icon="⚡️")
st.page_link("pages/2_husstands_el_forbrug.py", label="Gå til analyse af husstandens elforbrug", icon="🏠")


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

	render_car_charge_tab(df, from_date, to_date, _filter_df_by_view_range, udeladning_pris)

else:
	st.warning("Ingen data fundet. Gå til forsiden, og hent data først.")
