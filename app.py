import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import plotly.graph_objects as go

def fetch_el_price_range(start_date: str, end_date: str, zone: str = "DK2") -> pd.DataFrame:
    """Fetch hourly electricity prices from Elprisenligenu API."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    all_data = []

    for n in range((end - start).days + 1):
        current = start + timedelta(days=n)
        date_str = current.strftime("%Y/%m-%d")
        url = f"https://www.elprisenligenu.dk/api/v1/prices/{date_str}_{zone}.json"

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data)[['time_start', 'DKK_per_kWh']]
            df['time_start'] = pd.to_datetime(df['time_start'])
            all_data.append(df)
        except Exception as e:
            st.warning(f"Failed to fetch prices for {date_str}")
            
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

def fetch_tariff_data(access_token: str, points: list, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.Series:
    """Load manual tariff CSV (`tariffs_manual.csv`) and build hourly series.

    CSV columns: month_start,month_end,hour_start,hour_end,price
    month ranges may wrap (e.g. 10 to 3).
    """
    idx = pd.date_range(start=start_ts.floor('H'), end=end_ts.floor('H'), freq='H', tz=ZoneInfo('Europe/Copenhagen'))
    s = pd.Series(0.0, index=idx)
    try:
        tariffs = pd.read_csv('tariffs_manual.csv')
    except Exception as e:
        st.warning('Could not read tariffs_manual.csv: ' + str(e))
        return s

    for _, row in tariffs.iterrows():
        ms = int(row['month_start'])
        me = int(row['month_end'])
        hs = int(row['hour_start'])
        he = int(row['hour_end'])
        price = float(row['price'])

        if ms <= me:
            month_mask = (s.index.month >= ms) & (s.index.month <= me)
        else:
            month_mask = (s.index.month >= ms) | (s.index.month <= me)

        hour_mask = (s.index.hour >= hs) & (s.index.hour < he)
        mask = month_mask & hour_mask
        s.loc[mask] = price

    return s

def fetch_el_price_range(start_date: str, end_date: str, zone: str = "DK2") -> pd.DataFrame:
    """Fetch hourly electricity prices from Elprisenligenu API."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    all_data = []

    for n in range((end - start).days + 1):
        current = start + timedelta(days=n)
        date_str = current.strftime("%Y/%m-%d")
        url = f"https://www.elprisenligenu.dk/api/v1/prices/{date_str}_{zone}.json"

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data)[['time_start', 'DKK_per_kWh']]
            df['time_start'] = pd.to_datetime(df['time_start'])
            all_data.append(df)
        except Exception as e:
            st.warning(f"Failed to fetch prices for {date_str}")
            
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

def fetch_power_data(refresh_token: str, charge_threshold: float = 5.0, car_max_kwh: float = 11.0):
    """Fetch hourly power usage for last 30 days and merge with prices."""
    
    try:
        # Get access token
        r = requests.get('https://api.eloverblik.dk/customerapi/api/token',
                         headers={'Authorization': f'Bearer {refresh_token}'})
        if r.status_code != 200:
            st.error('❌ Token invalid or expired')
            return None

        access = r.json()['result']

        # Get metering points
        r = requests.get('https://api.eloverblik.dk/customerapi/api/meteringpoints/meteringpoints',
                         headers={'Authorization': f'Bearer {access}'})
        points = [m['meteringPointId'] for m in r.json()['result']]

        # Use provided from_date/to_date if set in outer scope (passed via closure),
        # otherwise default to last 30 days
        try:
            from_date
            to_date
        except NameError:
            to_date = datetime.now().date()
            from_date = to_date - timedelta(days=30)

        all_power_data = []
        
        with st.spinner('Fetching power usage data...'):
            for point in points:
                r = requests.post(f'https://api.eloverblik.dk/customerapi/api/meterdata/gettimeseries/{from_date}/{to_date}/Hour',
                                  json={'meteringPoints': {'meteringPoint': [point]}},
                                  headers={'Authorization': f'Bearer {access}'})
                data = r.json()
                
                if r.status_code != 200 or not data.get('result'):
                    continue
                    
                for result in data['result']:
                    doc = result.get('MyEnergyData_MarketDocument', {})
                    for ts in doc.get('TimeSeries', []):
                        for period in ts.get('Period', []):
                            start_str = period.get('timeInterval', {}).get('start', str(from_date))
                            start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                            # Convert UTC to Copenhagen timezone
                            start_date = start_date.astimezone(ZoneInfo('Europe/Copenhagen'))
                            
                            for idx, p in enumerate(period.get('Point', []), 0):
                                qty = float(p.get('out_Quantity.quantity', 0))
                                # Convert UTC to Copenhagen timezone
                                cph_start = start_date.astimezone(ZoneInfo('Europe/Copenhagen'))
                                hour_time = cph_start + timedelta(hours=idx)
                                all_power_data.append({
                                    'time': hour_time,
                                    'usage_kwh': qty
                                })

        if not all_power_data:
            st.error('No power usage data found')
            return None

        df_power = pd.DataFrame(all_power_data)
        df_power['time'] = pd.to_datetime(df_power['time'])
        
        # Fetch prices
        with st.spinner('Fetching electricity prices...'):
            df_prices = fetch_el_price_range(str(from_date), str(to_date), zone='DK2')
        
        if df_prices.empty:
            st.warning('Could not fetch price data')
            return df_power

        # Fetch tariff prices (hourly series) and merge
        with st.spinner('Fetching tariff prices...'):
            start_ts = df_power['time'].min()
            end_ts = df_power['time'].max()
            tariff_series = fetch_tariff_data(access, points, start_ts, end_ts)

        # Merge power data with prices
        df_merged = pd.merge(df_power, df_prices, left_on='time', right_on='time_start', how='left')

        try:
            tariff_series = tariff_series.tz_convert(ZoneInfo('Europe/Copenhagen'))
        except Exception:
            pass
        df_merged = df_merged.sort_values('time')
        df_merged['tariff_dkk_per_kwh'] = tariff_series.reindex(pd.DatetimeIndex(df_merged['time'])).fillna(0).values
        
        # Calculate costs
        df_merged['spot_cost_dkk'] = df_merged['usage_kwh'] * df_merged['DKK_per_kWh']
        df_merged['tariff_cost_dkk'] = df_merged['usage_kwh'] * df_merged['tariff_dkk_per_kwh']
        df_merged['total_cost_dkk'] = df_merged['spot_cost_dkk'] + df_merged['tariff_cost_dkk']
        
        # Select and order columns
        df_result = df_merged[['time', 'usage_kwh', 'DKK_per_kWh', 'tariff_dkk_per_kwh', 'total_cost_dkk']].copy()
        df_result.columns = ['time', 'usage_kwh', 'spot_pris', 'tarif_pris', 'total_udgift']
        df_result = df_result.sort_values('time').reset_index(drop=True)

        # Detect car charging and allocate kWh
        df_result['car_charging'] = df_result['usage_kwh'] >= float(charge_threshold)
        df_result['car_kwh'] = 0.0
        mask = df_result['car_charging']
        if mask.any():
            df_result.loc[mask, 'car_kwh'] = df_result.loc[mask, 'usage_kwh'].clip(upper=float(car_max_kwh))
        df_result['house_kwh'] = df_result['usage_kwh'] - df_result['car_kwh']

        return df_result
        
    except Exception as e:
        st.error(f'Error: {str(e)}')
        return None

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

if st.button('📊 Fetch Data', type='primary'):
    if not token:
        st.error('Please enter a token')
    else:
        df = fetch_power_data(token, charge_threshold, car_max_kwh)
        
        if df is not None and not df.empty:
            st.success('✅ Data fetched successfully!')
            
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
                if isinstance(view_range, tuple) and len(view_range) == 2:
                    vf_from, vf_to = view_range
                else:
                    vf_from = view_range
                    vf_to = view_range
                df_tab = df[(df['time'].dt.date >= vf_from) & (df['time'].dt.date <= vf_to)].copy()

                col1, col2 = st.columns(2)
                
                with col1:
                    # Usage chart
                    fig1 = go.Figure()
                    fig1.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['usage_kwh'], 
                                              mode='lines', name='Usage', fill='tozeroy'))
                    fig1.update_layout(title='Hourly Power Usage', xaxis_title='Time', 
                                      yaxis_title='Usage (kWh)', height=400)
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col2:
                    # Price chart (Spot + Tariff)
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['spot_pris'], 
                                              mode='lines', name='Spot Pris', line=dict(color='orange')))
                    fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['tarif_pris'], 
                                              mode='lines', name='Tarif Pris', line=dict(color='blue')))
                    fig2.update_layout(title='Hourly Electricity Prices', xaxis_title='Time', 
                                      yaxis_title='Price (DKK/kWh)', height=400)
                    st.plotly_chart(fig2, use_container_width=True)
                
                # Daily cost trend
                daily_cost = df_tab.groupby(df_tab['time'].dt.date).agg({
                    'total_udgift': 'sum',
                    'usage_kwh': 'sum',
                    'spot_pris': 'mean',
                    'tarif_pris': 'mean'
                }).reset_index()
                daily_cost.columns = ['date', 'total_cost', 'usage_kwh', 'avg_spot', 'avg_tarif']
                
                fig3 = go.Figure()
                fig3.add_trace(go.Bar(x=daily_cost['date'], y=daily_cost['total_cost'], name='Daily Cost'))
                fig3.update_layout(title='Daily Total Cost Trend', xaxis_title='Date', 
                                  yaxis_title='Cost (DKK)', height=400)
                st.plotly_chart(fig3, use_container_width=True)
            
            with tab2:
                view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab2')
                if isinstance(view_range, tuple) and len(view_range) == 2:
                    vf_from, vf_to = view_range
                else:
                    vf_from = view_range
                    vf_to = view_range
                df_tab = df[(df['time'].dt.date >= vf_from) & (df['time'].dt.date <= vf_to)].copy()

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
                if isinstance(view_range, tuple) and len(view_range) == 2:
                    vf_from, vf_to = view_range
                else:
                    vf_from = view_range
                    vf_to = view_range
                df_tab = df[(df['time'].dt.date >= vf_from) & (df['time'].dt.date <= vf_to)].copy()

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
                if isinstance(view_range, tuple) and len(view_range) == 2:
                    vf_from, vf_to = view_range
                else:
                    vf_from = view_range
                    vf_to = view_range
                df_tab = df[(df['time'].dt.date >= vf_from) & (df['time'].dt.date <= vf_to)].copy()

                hourly_stats = df_tab.copy()
                hourly_stats['hour_of_day'] = hourly_stats['time'].dt.hour
                avg_by_hour = hourly_stats.groupby('hour_of_day').agg({
                    'usage_kwh': 'mean',
                    'spot_pris': 'mean',
                    'tarif_pris': 'first',
                    'total_udgift': 'mean'
                }).reset_index()
                avg_by_hour.columns = ['Hour', 'Avg Usage (kWh)', 'Avg Spot Pris', 'Tarif Pris', 'Avg Total Cost (DKK)']
                st.dataframe(avg_by_hour, use_container_width=True)
                
                st.markdown('**Insights:**')
                if not hourly_stats.empty:
                    peak_hour = hourly_stats.groupby('hour_of_day')['spot_pris'].mean().idxmax()
                    st.info(f'⚠️ Most expensive hour: {peak_hour}:00 (avg Spot Pris {hourly_stats[hourly_stats["hour_of_day"]==peak_hour]["spot_pris"].mean():.3f} DKK/kWh)')

            with tab5:
                view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab5')
                if isinstance(view_range, tuple) and len(view_range) == 2:
                    vf_from, vf_to = view_range
                else:
                    vf_from = view_range
                    vf_to = view_range
                df_tab = df[(df['time'].dt.date >= vf_from) & (df['time'].dt.date <= vf_to)].copy()

                # Car charge dashboard
                df_car = df_tab.copy()
                # Ensure car_kwh exists
                if 'car_kwh' not in df_car.columns:
                    df_car['car_kwh'] = 0.0

                # Compute car cost = car_kwh * (spot + tariff)
                df_car['car_cost'] = df_car['car_kwh'] * (df_car['spot_pris'].fillna(0) + df_car['tarif_pris'].fillna(0))

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
