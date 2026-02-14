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

def fetch_power_data(refresh_token: str):
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

        # Get power data for last 30 days (HOURLY)
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

        # Merge power data with prices
        df_merged = pd.merge(df_power, df_prices, left_on='time', right_on='time_start', how='left')
        df_merged['cost_dkk'] = df_merged['usage_kwh'] * df_merged['DKK_per_kWh']
        
        # Select and order columns
        df_result = df_merged[['time', 'usage_kwh', 'DKK_per_kWh', 'cost_dkk']].copy()
        df_result.columns = ['hour', 'usage_kwh', 'price_dkk_per_kwh', 'cost_dkk']
        df_result = df_result.sort_values('hour').reset_index(drop=True)
        
        return df_result
        
    except Exception as e:
        st.error(f'Error: {str(e)}')
        return None

# Streamlit UI
st.set_page_config(page_title='Power Usage Monitor', layout='wide')
st.title('⚡ Power Usage & Cost Monitor')

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

if st.button('📊 Fetch Data', type='primary'):
    if not token:
        st.error('Please enter a token')
    else:
        df = fetch_power_data(token)
        
        if df is not None and not df.empty:
            st.success('✅ Data fetched successfully!')
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric('Total Usage', f"{df['usage_kwh'].sum():.1f} kWh")
            with col2:
                st.metric('Total Cost', f"{df['cost_dkk'].sum():.2f} DKK")
            with col3:
                st.metric('Avg Daily Cost', f"{df.groupby(df['hour'].dt.date)['cost_dkk'].sum().mean():.2f} DKK")
            with col4:
                st.metric('Avg Hourly Price', f"{df['price_dkk_per_kwh'].mean():.3f} DKK/kWh")
            
            st.divider()
            
            # Tabs for different views
            tab1, tab2, tab3, tab4 = st.tabs(['📈 Charts', '📋 Data Table', '📅 Daily Summary', '⏰ Hourly Stats'])
            
            with tab1:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Usage chart
                    fig1 = go.Figure()
                    fig1.add_trace(go.Scatter(x=df['hour'], y=df['usage_kwh'], 
                                              mode='lines', name='Usage', fill='tozeroy'))
                    fig1.update_layout(title='Hourly Power Usage', xaxis_title='Time', 
                                      yaxis_title='Usage (kWh)', height=400)
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col2:
                    # Price chart
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(x=df['hour'], y=df['price_dkk_per_kwh'], 
                                              mode='lines', name='Price', line=dict(color='orange')))
                    fig2.update_layout(title='Hourly Electricity Prices', xaxis_title='Time', 
                                      yaxis_title='Price (DKK/kWh)', height=400)
                    st.plotly_chart(fig2, use_container_width=True)
                
                # Daily cost trend
                daily_cost = df.groupby(df['hour'].dt.date).agg({
                    'cost_dkk': 'sum',
                    'usage_kwh': 'sum'
                }).reset_index()
                daily_cost.columns = ['date', 'cost_dkk', 'usage_kwh']
                
                fig3 = go.Figure()
                fig3.add_trace(go.Bar(x=daily_cost['date'], y=daily_cost['cost_dkk'], name='Daily Cost'))
                fig3.update_layout(title='Daily Cost Trend', xaxis_title='Date', 
                                  yaxis_title='Cost (DKK)', height=400)
                st.plotly_chart(fig3, use_container_width=True)
            
            with tab2:
                st.dataframe(df, use_container_width=True, height=600)
                
                # Download button
                csv = df.to_csv(index=False)
                st.download_button(
                    label='📥 Download as CSV',
                    data=csv,
                    file_name=f'power_usage_{datetime.now().date()}.csv',
                    mime='text/csv'
                )
            
            with tab3:
                daily_summary = df.groupby(df['hour'].dt.date).agg({
                    'usage_kwh': 'sum',
                    'cost_dkk': 'sum',
                    'price_dkk_per_kwh': 'mean'
                }).reset_index()
                daily_summary.columns = ['Date', 'Usage (kWh)', 'Cost (DKK)', 'Avg Price (DKK/kWh)']
                st.dataframe(daily_summary, use_container_width=True)
            
            with tab4:
                hourly_stats = df.copy()
                hourly_stats['hour_of_day'] = hourly_stats['hour'].dt.hour
                avg_by_hour = hourly_stats.groupby('hour_of_day').agg({
                    'usage_kwh': 'mean',
                    'price_dkk_per_kwh': 'mean',
                    'cost_dkk': 'mean'
                }).reset_index()
                avg_by_hour.columns = ['Hour', 'Avg Usage (kWh)', 'Avg Price (DKK/kWh)', 'Avg Cost (DKK)']
                st.dataframe(avg_by_hour, use_container_width=True)
                
                st.markdown('**Insights:**')
                peak_hour = hourly_stats.groupby('hour_of_day')['price_dkk_per_kwh'].mean().idxmax()
                st.info(f'⚠️ Most expensive hour: {peak_hour}:00 (avg {hourly_stats[hourly_stats["hour_of_day"]==peak_hour]["price_dkk_per_kwh"].mean():.3f} DKK/kWh)')
