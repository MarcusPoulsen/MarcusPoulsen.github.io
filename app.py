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

# Reduce top space above title and vertically center the button using custom CSS
st.markdown(
    """
    <style>
        /* Remove top padding and margin from main container */
        .main .block-container {
            padding-top: 1rem !important;
        }
        /* Remove Streamlit default header space */
        header {margin-bottom: 0rem !important;}
        /* Vertically center the button in the last column */
        div[data-testid="column"]:last-child button {
            margin-top: 16px !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.set_page_config(page_title='Elbil strømberegner', layout='wide')
st.title('⚡ Strømforbrug og omkostninger - Eloverblik Dashboard')

st.markdown('Det kan være uoverskueligt at vurdere, hvor meget man reelt betaler for sin strøm, når man hjemmeoplader sin elbil. Denne app forsøger at estimere, hvornår elbilen lader op, og dermed hvad prisen du selv betaler for strømmen har været. Det kan herefter sammenlignes, med den refusion man modtager fra fx Clever.' \
'Data hentes fra Eloverblik API og inkluderer både spotpris, tariffer og afgifter. For at finde de tidspunkter Elbilen lader op, antager vi at et forbrug over fx 5kwh på en time må indikere at elbilen lader op. Denne antagelse kan justeres.' \
' Klik her for at hente "API token": https://www.eloverblik.dk -> Log ind -> API Adgang -> Opret token')


# Date range defaults
today = datetime.now().date()
default_from = today - timedelta(days=30)


# Five columns: token, periode, elbil oplader flag, max opladningshastighed, beregn knap
col_token, col_date, col_charge, col_max, col_btn = st.columns(5)
with col_token:
    token = st.text_input(
        'Eloverblik token',
        placeholder='Indtast din token fra eloverblik',
        type='password',
        help='Klik her for at hente en: https://www.eloverblik.dk -> Log ind -> API Adgang -> Opret token -> indtast token her. Din token gemmes ikke og bruges kun til denne session.'
    )
with col_date:
    date_range = st.date_input('Periode', value=(default_from, today), help='Vælg start- og slutdato for perioden', key='periode_date_input')
    if isinstance(date_range, tuple) and len(date_range) == 2:
        from_date, to_date = date_range
    else:
        from_date = date_range
        to_date = date_range
with col_charge:
    charge_threshold = st.number_input(
        'Elbil oplader flag',
        min_value=0.0,
        value=5.0,
        step=0.1,
        help='Indsæt Kwh hvor du er sikker på at din elbil lader den time, fx 5 kwh hvis du ved at resten af huset max kan bruge 4,5 kwh'
    )
with col_max:
    car_max_kwh = st.number_input(
        'Max opladningshastighed (kWh)',
        min_value=0.0,
        value=11.0,
        step=0.1,
        help='Maksimalt antal kWh bilen kan tage per time (fx 11)'
    )
with col_btn:
    fetch_btn = st.button('📊 Hent data og beregn udgifter', type='primary')


# Use the button from the new column layout
if fetch_btn:
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

# Persist fetched data across reruns so date filters don't force refetch
if 'df_data' not in st.session_state:
    st.session_state['df_data'] = pd.DataFrame()

if 'last_token' not in st.session_state:
    st.session_state['last_token'] = None

# Render results if we have cached data
if not st.session_state['df_data'].empty:
    df = st.session_state['df_data']
    # Ensure afgift is included in per-kWh total price used across charts/tables
    df['spot_pris'] = df.get('spot_pris', pd.Series(0.0))
    df['tarif_pris'] = df.get('tarif_pris', pd.Series(0.0))
    df['afgift_pris'] = df.get('afgift_pris', pd.Series(0.0))
    df['total_pris_per_kwh'] = df['spot_pris'].fillna(0) + df['tarif_pris'].fillna(0) + df['afgift_pris'].fillna(0)

    st.markdown(f"### Hustandsforbrug og udgifter {from_date} til {to_date}")
    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric('Total forbrug for hele perioden', f"{df['usage_kwh'].sum():.1f} kWh")
    with col2:
        st.metric('Total udgift for hele perioden', f"{df['total_udgift'].sum():.2f} DKK")
    with col3:
        st.metric('Gennemsnitlig daglig udgift', f"{df.groupby(df['time'].dt.date)['total_udgift'].sum().mean():.2f} DKK")
    with col4:
        st.metric('Gennemsnitlig spotpris for hele perioden', f"{df['spot_pris'].mean():.3f} DKK/kWh")
    with col5:
        st.metric('Gennemsnitlig totalpris for hele perioden', f"{df['total_pris_per_kwh'].mean():.3f} DKK/kWh")
    
    st.divider()

    st.markdown(f"## Vælg mellem forskellige visninger og analyser af dataen nedenfor")
    # Tabs for different views (Car Charge first)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(['🚗 Clever refusion vs pris på opladning', '📈 Strømforbrug figurer', '📊 Data Deep dive', '📅 Daily Summary', '⏰ Hourly Stats'])

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