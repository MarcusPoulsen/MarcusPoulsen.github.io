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

    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs(['📈 Charts', '📋 Data Table', '📅 Daily Summary', '⏰ Hourly Stats', '🚗 Car Charge'])
            
    with tab1:
        # Per-tab view filter
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab1')
        df_tab = _filter_df_by_view_range(df, view_range)

        col1, col2 = st.columns(2)

        with col1:
            # Usage chart
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['usage_kwh'], mode='lines', name='Usage', fill='tozeroy'))
            fig1.update_layout(title='Hourly Power Usage', xaxis_title='Time', yaxis_title='Usage (kWh)', height=400)
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            # Price chart (Spot + Tariff)
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['spot_pris'], mode='lines', name='Spot Pris', line=dict(color='orange')))
            fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['tarif_pris'], mode='lines', name='Tarif Pris', line=dict(color='blue')))
            # Show afgift and combined total price per kWh
            if 'afgift_pris' in df_tab.columns:
                fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['afgift_pris'], mode='lines', name='Afgift (tax)', line=dict(color='purple', dash='dot')))
            fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['total_pris_per_kwh'], mode='lines', name='Total Pris (DKK/kWh)', line=dict(color='black', width=2)))
            fig2.update_layout(title='Hourly Electricity Prices', xaxis_title='Time', yaxis_title='Price (DKK/kWh)', height=400)
            st.plotly_chart(fig2, use_container_width=True)

        # Daily cost trend
        daily_cost = df_tab.groupby(df_tab['time'].dt.date).agg({
            'total_udgift': 'sum',
            'usage_kwh': 'sum',
            'spot_pris': 'mean',
            'tarif_pris': 'mean',
            'total_pris_per_kwh': 'mean'
        }).reset_index()
        daily_cost.columns = ['date', 'total_cost', 'usage_kwh', 'avg_spot', 'avg_tarif', 'avg_total_pris']

        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=daily_cost['date'], y=daily_cost['total_cost'], name='Daily Cost'))
        fig3.update_layout(title='Daily Total Cost Trend', xaxis_title='Date', yaxis_title='Cost (DKK)', height=400)
        st.plotly_chart(fig3, use_container_width=True)
            
    with tab2:
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab2')
        df_tab = _filter_df_by_view_range(df, view_range)

        st.dataframe(df_tab, use_container_width=True, height=600)

        # Download button
        csv = df_tab.to_csv(index=False)
        st.download_button(
            label='📥 Download as CSV',
            data=csv,
            file_name=f'power_usage_{datetime.now().date()}.csv',
            mime='text/csv'
        )
            
    with tab3:
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab3')
        df_tab = _filter_df_by_view_range(df, view_range)

        daily_summary = df_tab.groupby(df_tab['time'].dt.date).agg({
            'usage_kwh': 'sum',
            'total_udgift': 'sum',
            'spot_pris': 'mean',
            'tarif_pris': 'first'
        }).reset_index()
        daily_summary.columns = ['Date', 'Usage (kWh)', 'Total Cost (DKK)', 'Avg Spot Pris', 'Tarif Pris']
        st.dataframe(daily_summary, use_container_width=True)
            
    with tab4:
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab4')
        df_tab = _filter_df_by_view_range(df, view_range)

        hourly_stats = df_tab.copy()
        hourly_stats['hour_of_day'] = hourly_stats['time'].dt.hour
        avg_by_hour = hourly_stats.groupby('hour_of_day').agg({
            'usage_kwh': 'mean',
            'spot_pris': 'mean',
            'tarif_pris': 'first',
            'total_pris_per_kwh': 'mean',
            'total_udgift': 'mean'
        }).reset_index()
        avg_by_hour.columns = ['Hour', 'Avg Usage (kWh)', 'Avg Spot Pris', 'Tarif Pris', 'Avg Total Pris (DKK/kWh)', 'Avg Total Cost (DKK)']
        st.dataframe(avg_by_hour, use_container_width=True)

        st.markdown('**Insights:**')
        if not hourly_stats.empty:
            peak_hour = hourly_stats.groupby('hour_of_day')['spot_pris'].mean().idxmax()
            st.info(f'⚠️ Most expensive hour: {peak_hour}:00 (avg Spot Pris {hourly_stats[hourly_stats["hour_of_day"]==peak_hour]["spot_pris"].mean():.3f} DKK/kWh)')

    with tab5:
        view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab5')
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
            monthly_car['month'] = monthly_car['time'].dt.to_period('M').astype(str)
            monthly_car['avg_price'] = monthly_car.apply(lambda r: (r['car_cost'] / r['car_kwh']) if r['car_kwh'] > 0 else 0.0, axis=1)
            monthly_table = monthly_car[['month', 'car_kwh', 'avg_price', 'car_cost']].copy()
            monthly_table.columns = ['month', 'kwh_charged', 'average_price', 'total_price']
            # Allow per-month Clever reimbursement rate input and compute reimbursed/net totals
            st.markdown('### Månedligt opladningsoversigt')

            reimbursed_vals = []
            kwh_clever_vals = []
            extra_kwh_vals = []
            extra_cost_vals = []
            net_vals = []
            adjusted_total_vals = []

            for i, r in monthly_table.iterrows():
                m = r['month']
                key_rate = f'clever_rate_{m}'
                key_kwh = f'clever_kwh_{m}'

                # Default rate/kWh to 0 or previous session value
                rate_default = float(st.session_state.get(key_rate, 0.0))
                kwh_default = float(st.session_state.get(key_kwh, r['kwh_charged']))

                col_a, col_b, col_c = st.columns([2, 2, 2])
                with col_a:
                    st.write(m)
                with col_b:
                    st.write(f"{r['kwh_charged']:.2f} kWh (detected)")
                with col_c:
                    # reimbursement rate in DKK/kWh — use widget return value (widget stores into session_state)
                    rate_val = st.number_input(f'Clever sats (DKK/kWh) for {m}', min_value=0.0, value=rate_default, format="%.2f", key=key_rate)

                # Additional input: kWh according to Clever
                kwh_col1, kwh_col2 = st.columns([2, 2])
                with kwh_col1:
                    kwh_clever = st.number_input(f'kWh ifølge Clever ({m})', min_value=0.0, value=kwh_default, format="%.2f", key=key_kwh)
                with kwh_col2:
                    st.write(f"Gennemsnitspris: {r['average_price']:.4f} DKK/kWh")

                # Compute correction kWh (Clever reported minus detected) — allow negative
                korrektion_kwh = float(kwh_clever) - float(r['kwh_charged'])
                korrektion_cost = korrektion_kwh * float(r['average_price'])

                # Adjusted total price includes cost for the correction kWh priced at avg_price
                adjusted_total = float(r['total_price']) + korrektion_cost

                reimbursed = float(kwh_clever) * float(rate_val)
                net = adjusted_total - reimbursed

                # Collect values for table
                reimbursed_vals.append(reimbursed)
                kwh_clever_vals.append(kwh_clever)
                # store signed correction (can be negative)
                extra_kwh_vals.append(korrektion_kwh)
                extra_cost_vals.append(korrektion_cost)
                adjusted_total_vals.append(adjusted_total)
                net_vals.append(net)

            monthly_table['kwh_clever'] = kwh_clever_vals
            monthly_table['korrektion_kwh_clever'] = extra_kwh_vals
            monthly_table['korrektion_cost'] = extra_cost_vals
            monthly_table['adjusted_total'] = adjusted_total_vals
            monthly_table['reimbursed'] = reimbursed_vals
            monthly_table['net_price'] = net_vals
            display_table = monthly_table[['month', 'kwh_charged', 'kwh_clever', 'korrektion_kwh_clever', 'average_price', 'total_price', 'korrektion_cost', 'adjusted_total', 'reimbursed', 'net_price']].copy()
            st.dataframe(display_table, use_container_width=True)
            csv = display_table.to_csv(index=False)
            st.download_button('📥 Download monthly CSV', csv, file_name=f'monthly_car_{datetime.now().date()}.csv', mime='text/csv')
        else:
            st.info('Ingen månedlig opladningsdata i valgt periode')
