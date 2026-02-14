#!/usr/bin/env python3
import requests
import pandas as pd
from datetime import datetime, timedelta

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
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data)[['time_start', 'DKK_per_kWh']]
            df['time_start'] = pd.to_datetime(df['time_start'])
            all_data.append(df)
        except Exception as e:
            print(f"Failed for {date_str}: {e}")
            
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

def fetch_power_data(token_file='token.txt'):
    """Fetch hourly power usage for last 30 days and merge with prices."""
    
    with open(token_file) as f:
        refresh = f.read().strip()

    # Get access token
    r = requests.get('https://api.eloverblik.dk/customerapi/api/token',
                     headers={'Authorization': f'Bearer {refresh}'})
    if r.status_code != 200:
        print(f'Error: {r.status_code} - Token invalid/expired')
        exit(1)

    access = r.json()['result']

    # Get metering points
    r = requests.get('https://api.eloverblik.dk/customerapi/api/meteringpoints/meteringpoints',
                     headers={'Authorization': f'Bearer {access}'})
    points = [m['meteringPointId'] for m in r.json()['result']]
    print(f'Found {len(points)} metering point(s)\n')

    # Get power data for last 30 days (HOURLY)
    to_date = datetime.now().date()
    from_date = to_date - timedelta(days=30)

    all_power_data = []
    
    for point in points:
        # Request HOUR aggregation instead of Day
        r = requests.post(f'https://api.eloverblik.dk/customerapi/api/meterdata/gettimeseries/{from_date}/{to_date}/Hour',
                          json={'meteringPoints': {'meteringPoint': [point]}},
                          headers={'Authorization': f'Bearer {access}'})
        data = r.json()
        
        if r.status_code != 200 or not data.get('result'):
            print(f'No data for {point}')
            continue
            
        for result in data['result']:
            doc = result.get('MyEnergyData_MarketDocument', {})
            for ts in doc.get('TimeSeries', []):
                for period in ts.get('Period', []):
                    start_str = period.get('timeInterval', {}).get('start', str(from_date))
                    # Parse ISO format with timezone
                    start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    
                    for idx, p in enumerate(period.get('Point', []), 0):
                        qty = float(p.get('out_Quantity.quantity', 0))
                        hour_time = start_date + timedelta(hours=idx)
                        all_power_data.append({
                            'time': hour_time,
                            'usage_kwh': qty
                        })

    # Create DataFrame from power data
    df_power = pd.DataFrame(all_power_data)
    if df_power.empty:
        print('No power data found')
        return None
    
    df_power['time'] = pd.to_datetime(df_power['time'])
    
    # Fetch prices
    print('Fetching electricity prices...')
    df_prices = fetch_el_price_range(str(from_date), str(to_date), zone='DK2')
    
    # Merge power data with prices
    df_merged = pd.merge(df_power, df_prices, left_on='time', right_on='time_start', how='left')
    df_merged['cost_dkk'] = df_merged['usage_kwh'] * df_merged['DKK_per_kWh']
    
    # Select and order columns
    df_result = df_merged[['time', 'usage_kwh', 'DKK_per_kWh', 'cost_dkk']].copy()
    df_result.columns = ['hour', 'usage_kwh', 'price_dkk_per_kwh', 'cost_dkk']
    df_result = df_result.sort_values('hour').reset_index(drop=True)
    
    print(f'\nFetched {len(df_result)} hours of data from {from_date} to {to_date}\n')
    print(df_result.to_string(index=False))
    print(f'\nTotal usage: {df_result["usage_kwh"].sum():.2f} kWh')
    print(f'Total cost: {df_result["cost_dkk"].sum():.2f} DKK')
    
    return df_result

if __name__ == '__main__':
    df = fetch_power_data()

