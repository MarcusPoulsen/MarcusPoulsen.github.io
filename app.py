import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
from fetch_power_data import fetch_power_data


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

st.set_page_config(page_title='Elbil strømberegner', page_icon='⚡', layout='wide', initial_sidebar_state='collapsed')
st.sidebar.title('Forside')
st.sidebar.success("Select a demo above.")
st.title('⚡ Strømforbrug og omkostninger - Eloverblik Dashboard')
st.markdown("""
Det kan være svært at gennemskue, hvad du reelt betaler for strømmen, når du oplader din elbil derhjemme. 
Denne app estimerer, hvornår bilen lader, og beregner hvad strømmen i netop de timer har kostet dig.
Data hentes fra Eloverblik API og inkluderer spotpris, tariffer og afgifter. 
Opladning identificeres ved timeforbrug over fx 5 kWh – en grænse, som kan justeres.
Resultatet kan sammenlignes med den refusion, du modtager fra fx Clever, så du kan se din faktiske nettoudgift.
Klik her for at hente "API token": https://www.eloverblik.dk  -> Log ind → API Adgang → Opret token
""")


# Date range defaults
today = datetime.now().date()
default_from = today - timedelta(days=30)


# Five columns: token, periode, elbil oplader flag, max opladningshastighed, beregn knap
col_token, col_date, col_charge, col_max, col_udelad_pris, col_btn = st.columns(6)
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
with col_udelad_pris:
    udeladning_pris = st.number_input(
        'Antaget udeladning pris (DKK)',
        min_value=0.0,
        value=3.5,
        step=0.1,
        help='Indtast den pris du antager for udeladning (fx 3,5 DKK pr. kWh)'
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
            st.session_state['udeladning_pris'] = udeladning_pris
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

    st.markdown("## Gå til siden 'Data Analyse' for at se detaljerede analyser og visninger af dine data.")
    st.info("Klik på 'Data Analyse' i menuen til venstre for at se tabeller, grafer og statistik.")
    st.page_link("pages/elbil_opladning.py", label="Gå til Data Analyse", icon="📊")