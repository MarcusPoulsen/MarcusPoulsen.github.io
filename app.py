import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
from fetch_power_data import fetch_power_data

# Import tab modules
from tabs.car_charge_tab import render as render_car_charge_tab
from tabs.charts_tab import render as render_charts_tab
from tabs.data_table_tab import render as render_data_table_tab
from tabs.daily_summary_tab import render as render_daily_summary_tab
from tabs.hourly_stats_tab import render as render_hourly_stats_tab


def _filter_df_by_view_range(df, view_range):
    """Safely filter `df` by a Streamlit `date_input` value which may be a single
    date, a tuple of (from, to), or contain None while the user is selecting.
    Returns an unmodified df if parsing fails.
    """
    try:
        if isinstance(view_range, tuple) and len(view_range) == 2:
            vf_from, vf_to = view_range
        else:
            vf_from = view_range
            vf_to = view_range

        # If both are None, return full df
        if vf_from is None and vf_to is None:
            return df

        # Normalize to date objects when possible
        if vf_from is not None and not isinstance(vf_from, date):
            vf_from = pd.to_datetime(vf_from).date()
        if vf_to is not None and not isinstance(vf_to, date):
            vf_to = pd.to_datetime(vf_to).date()

        # Fill open-ended ranges with data bounds
        if vf_from is None:
            vf_from = df['time'].dt.date.min()
        if vf_to is None:
            vf_to = df['time'].dt.date.max()

        # Ensure ordering
        if vf_from > vf_to:
            vf_from, vf_to = vf_to, vf_from

        return df[(df['time'].dt.date >= vf_from) & (df['time'].dt.date <= vf_to)].copy()
    except Exception:
        return df

# Streamlit UI
st.set_page_config(page_title='Power Usage Monitor', layout='wide')
st.title('⚡ Strømforbrug og omkostninger - Eloverblik Dashboard')

# Date range selector for period filtering
today = datetime.now().date()
default_from = today - timedelta(days=30)
date_range = st.date_input('Periode', value=(default_from, today), help='Vælg start- og slutdato for perioden')
if isinstance(date_range, tuple) and len(date_range) == 2:
    from_date, to_date = date_range
else:
    from_date = date_range
    to_date = date_range

st.markdown('Overvåg dit husstands strømforbrug og omkostninger. For at få en indikation på, hvad opladning af elbil koster, kan du sætte et kWh threshold for at identificere timer hvor bilen sandsynligvis lader. Data hentes fra Eloverblik API og inkluderer både spotpris og tariffer. Lige nu bruges en Zone DK2 (øst Danmark)')

st.divider()

# Token input (with security tip)
token = st.text_input(
    'Indtast din Eloverblik refresh token:, klik her for at hente en: https://www.eloverblik.dk -> Log ind -> API Adgang -> Opret token -> indtast token her',
    type='password',
    help='Din token gemmes ikke og bruges kun til denne session'
)

# Inputs for electric car detection
charge_threshold = st.number_input(
    'Elbil oplader flag',
    min_value=0.0,
    value=5.0,
    step=0.1,
    help='Indsæt Kwh hvor du er sikker på at din elbil lader den time, fx 5 kwh hvis du ved at resten af huset max kan bruge 4,5 kwh'
)
car_max_kwh = st.number_input(
    'Max opladningshastighed (kWh)',
    min_value=0.0,
    value=11.0,
    step=0.1,
    help='Maksimalt antal kWh bilen kan tage per time (fx 11)'
)

# Persist fetched data across reruns so date filters don't force refetch
if 'df_data' not in st.session_state:
    st.session_state['df_data'] = pd.DataFrame()

if 'last_token' not in st.session_state:
    st.session_state['last_token'] = None

if st.button('📊 Fetch Data', type='primary'):
    if not token:
        st.error('Please enter a token')
    else:
        df = fetch_power_data(token, charge_threshold, car_max_kwh, from_date, to_date)
        if df is not None and not df.empty:
            st.session_state['df_data'] = df
            st.session_state['last_token'] = token
            st.success('✅ Data fetched and cached for this session')
        else:
            st.warning('No data fetched')

# Render results if we have cached data
if not st.session_state['df_data'].empty:
    df = st.session_state['df_data']
    # Ensure afgift is included in per-kWh total price used across charts/tables
    df['spot_pris'] = df.get('spot_pris', pd.Series(0.0))
    df['tarif_pris'] = df.get('tarif_pris', pd.Series(0.0))
    df['afgift_pris'] = df.get('afgift_pris', pd.Series(0.0))
    df['total_pris_per_kwh'] = df['spot_pris'].fillna(0) + df['tarif_pris'].fillna(0) + df['afgift_pris'].fillna(0)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric('Total Usage', f"{df['usage_kwh'].sum():.1f} kWh")
    with col2:
        st.metric('Total Cost', f"{df['total_udgift'].sum():.2f} DKK")
    with col3:
        st.metric('Avg Daily Cost', f"{df.groupby(df['time'].dt.date)['total_udgift'].sum().mean():.2f} DKK")
    with col4:
        st.metric('Avg Spot Price', f"{df['spot_pris'].mean():.3f} DKK/kWh")
    
    st.divider()

    # Tabs for different views (Car Charge first)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(['🚗 Car Charge', '📈 Charts', '📊 Data Table', '📅 Daily Summary', '⏰ Hourly Stats'])

    with tab1:
        render_car_charge_tab(df, from_date, to_date, _filter_df_by_view_range)
    with tab2:
        render_charts_tab(df, from_date, to_date, _filter_df_by_view_range)
    with tab3:
        render_data_table_tab(df, from_date, to_date, _filter_df_by_view_range)
    with tab4:
        render_daily_summary_tab(df, from_date, to_date, _filter_df_by_view_range)
    with tab5:
        render_hourly_stats_tab(df, from_date, to_date, _filter_df_by_view_range)