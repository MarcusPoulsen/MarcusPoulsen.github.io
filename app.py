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

# Streamlit UI
st.set_page_config(page_title='Power Usage Monitor', layout='wide')
st.title('⚡ Power Usage & Cost Monitor')

# Date range selector for period filtering
today = datetime.now().date()
default_from = today - timedelta(days=30)
date_range = st.date_input('Periode', value=(default_from, today), help='Vælg start- og slutdato for perioden')
if isinstance(date_range, tuple) and len(date_range) == 2:
    from_date, to_date = date_range
else:
    from_date = date_range
    to_date = date_range

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown('Monitor your household power usage and costs for the last 30 days')
with col2:
    st.markdown('**Zone:** DK2 (Eastern Denmark)')

st.divider()

# Token input (with security tip)
token = st.text_input(
    'Enter your Eloverblik refresh token:',
    type='password',
    help='Your token is not stored and only used for this session'
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(['🚗 Car Charge', '📈 Charts', '📋 Data Table', '📅 Daily Summary', '⏰ Hourly Stats'])

    with tab1:
        # --- Car Charge dashboard code (was tab5) ---
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab1')
        df_tab = _filter_df_by_view_range(df, view_range)

        # Car charge dashboard
        df_car = df_tab.copy()
        # Ensure car_kwh exists
        if 'car_kwh' not in df_car.columns:
            df_car['car_kwh'] = 0.0

        # Compute car cost = car_kwh * (spot + tariff + afgift)
        if 'afgift_pris' in df_car.columns:
            afgift_series = df_car['afgift_pris'].fillna(0)
        else:
            afgift_series = 0.0

        df_car['car_cost'] = df_car['car_kwh'] * (
            df_car['spot_pris'].fillna(0) + df_car['tarif_pris'].fillna(0) + afgift_series
        )

        daily_car = df_car.groupby(df_car['time'].dt.date).agg({
            'car_cost': 'sum',
            'car_kwh': 'sum'
        }).reset_index()
        daily_car.columns = ['date', 'total_charge_cost', 'total_charge_kwh']

        # Metrics / callouts
        c1, c2 = st.columns(2)
        with c1:
            st.metric('Total charge cost', f"{daily_car['total_charge_cost'].sum():.2f} DKK")
        with c2:
            st.metric('Total kWh charged', f"{daily_car['total_charge_kwh'].sum():.2f} kWh")

        st.divider()

        # Plot: bar = cost, line = kWh
        fig_car = go.Figure()
        fig_car.add_trace(go.Bar(x=daily_car['date'], y=daily_car['total_charge_cost'], name='Charge Cost (DKK)', marker_color='green'))
        fig_car.add_trace(go.Line(x=daily_car['date'], y=daily_car['total_charge_kwh'], name='Charged kWh', yaxis='y2', line=dict(color='red', width=3)))
        fig_car.update_layout(
            title='Daily Charge Cost and kWh',
            xaxis_title='Date',
            yaxis=dict(title='Cost (DKK)'),
            yaxis2=dict(title='kWh', overlaying='y', side='right'),
            height=450
        )
        st.plotly_chart(fig_car, use_container_width=True)

        # Monthly aggregation table: month, kwh charged, average price (incl tariffs), total price
        monthly_car = df_car.set_index('time').resample('M').agg({'car_kwh': 'sum', 'car_cost': 'sum'}).reset_index()
        if not monthly_car.empty:
            # Format month as MM-YY to match clever_tilbagebetaling.csv
            monthly_car['month'] = monthly_car['time'].dt.strftime('%m-%y')
            monthly_car['avg_price'] = monthly_car.apply(lambda r: (r['car_cost'] / r['car_kwh']) if r['car_kwh'] > 0 else 0.0, axis=1)
            monthly_table = monthly_car[['month', 'car_kwh', 'avg_price', 'car_cost']].copy()
            monthly_table.columns = ['month', 'kwh_charged', 'average_price', 'total_price']
            st.markdown('### Månedligt opladningsoversigt')

            # Load Clever sats from CSV
            clever_sats_df = pd.read_csv('clever_tilbagebetaling.csv')
            # Ensure month column is string and in MM-YY format
            clever_sats_df['month'] = clever_sats_df['month'].astype(str)

            # Merge monthly_table with clever_sats_df on 'month'
            merged = pd.merge(monthly_table, clever_sats_df, on='month', how='left')
            merged['sats'] = merged['sats'].astype(float).fillna(0.0)
            merged = merged.rename(columns={'sats': 'clever_rate'})

            # Prepare editable input columns for the table (only clever_kwh and udeladning_kwh)
            clever_kwh_col = []
            udeladning_kwh_col = []
            for i, r in merged.iterrows():
                m = r['month']
                key_kwh = f'clever_kwh_{m}'
                key_udelad = f'udeladning_kwh_{m}'
                clever_kwh_col.append(float(st.session_state.get(key_kwh, r['kwh_charged'])))
                udeladning_kwh_col.append(float(st.session_state.get(key_udelad, 0.0)))

            merged['clever_kwh'] = clever_kwh_col
            merged['udeladning_kwh'] = udeladning_kwh_col

            # Use st.data_editor for a single input table (only clever_kwh and udeladning_kwh editable)
            edited = st.data_editor(
                merged,
                column_config={
                    'clever_rate': st.column_config.NumberColumn('Clever sats (DKK/kWh)', min_value=0.0, step=0.01, format='%.2f', disabled=True),
                    'clever_kwh': st.column_config.NumberColumn('kWh ifølge Clever', min_value=0.0, step=0.01, format='%.2f'),
                    'udeladning_kwh': st.column_config.NumberColumn('Udeladning kWh', min_value=0.0, step=0.01, format='%.2f'),
                },
                disabled=['month', 'kwh_charged', 'average_price', 'total_price', 'clever_rate'],
                hide_index=True,
                use_container_width=True,
                key='monthly_car_editor'
            )

            # Save edited values back to session_state for persistence
            for i, r in edited.iterrows():
                m = r['month']
                st.session_state[f'clever_kwh_{m}'] = r['clever_kwh']
                st.session_state[f'udeladning_kwh_{m}'] = r['udeladning_kwh']

            # Compute all derived columns for display and download
            display_table = merged.copy()
            display_table['korrektion_kwh_clever'] = display_table['clever_kwh'] - display_table['kwh_charged']
            display_table['korrektion_cost'] = display_table['korrektion_kwh_clever'] * display_table['average_price']
            display_table['udeladning_cost'] = display_table['udeladning_kwh'] * 3.5
            display_table['adjusted_total'] = display_table['total_price'] + display_table['korrektion_cost']
            display_table['reimbursed'] = display_table['clever_kwh'] * display_table['clever_rate']
            display_table['net_price'] = display_table['adjusted_total'] - display_table['reimbursed']
            display_table['clever_abbonnemnt'] = 799.0
            display_table['total_udgift_ved_clever_abbonemnt'] = display_table['net_price'] + display_table['clever_abbonnemnt']

            # Show the calculated table below the editor
            st.dataframe(display_table[[
                'month', 'kwh_charged', 'clever_kwh', 'korrektion_kwh_clever',
                'average_price', 'total_price', 'korrektion_cost', 'adjusted_total',
                'reimbursed', 'net_price', 'clever_abbonnemnt', 'total_udgift_ved_clever_abbonemnt',
                'udeladning_kwh', 'udeladning_cost'
            ]], use_container_width=True)

            csv = display_table[[
                'month', 'kwh_charged', 'clever_kwh', 'korrektion_kwh_clever',
                'average_price', 'total_price', 'korrektion_cost', 'adjusted_total',
                'reimbursed', 'net_price', 'clever_abbonnemnt', 'total_udgift_ved_clever_abbonemnt',
                'udeladning_kwh', 'udeladning_cost'
            ]].to_csv(index=False)
            st.download_button('📥 Download monthly CSV', csv, file_name=f'monthly_car_{datetime.now().date()}.csv', mime='text/csv')
        else:
            st.info('Ingen månedlig opladningsdata i valgt periode')

    # --- The rest of the tabs: Charts, Data Table, Daily Summary, Hourly Stats ---
    with tab2:
        # (was tab1: Charts)
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab2')
        df_tab = _filter_df_by_view_range(df, view_range)
        # ...existing Charts code...

    with tab3:
        # (was tab2: Data Table)
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab3')
        df_tab = _filter_df_by_view_range(df, view_range)
        # ...existing Data Table code...

    with tab4:
        # (was tab3: Daily Summary)
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab4')
        df_tab = _filter_df_by_view_range(df, view_range)
        # ...existing Daily Summary code...

    with tab5:
        # (was tab4: Hourly Stats)
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab5')
        df_tab = _filter_df_by_view_range(df, view_range)
        # ...existing Hourly Stats code...