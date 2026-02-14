#!/usr/bin/env python3
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
        print('Could not read tariffs_manual.csv:', e)
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

def fetch_power_data(refresh_token=None, charge_threshold: float = 5.0, car_max_kwh: float = 11.0, from_date=None, to_date=None):
    """Fetch hourly power usage for a period and merge with prices.

    If `refresh_token` is None, the function will read 'token.txt'.
    """
    if refresh_token is None:
        with open('token.txt') as f:
            refresh = f.read().strip()
    else:
        refresh = refresh_token

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

    # Determine date range
    if to_date is None or from_date is None:
        to_date = datetime.now().date() if to_date is None else to_date
        from_date = (to_date - timedelta(days=30)) if from_date is None else from_date

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
                    # Parse ISO format with timezone (UTC) and convert to Copenhagen time
                    start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    start_date = start_date.astimezone(ZoneInfo('Europe/Copenhagen'))
                    
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
    
    if df_prices.empty:
        print('Warning: Could not fetch price data')
        return df_power
    
    # Fetch tariff prices (build hourly series)
    print('Fetching tariff prices...')
    start_ts = df_power['time'].min()
    end_ts = df_power['time'].max()
    tariff_series = fetch_tariff_data(access, points, start_ts, end_ts)

    # Merge power data with prices
    df_merged = pd.merge(df_power, df_prices, left_on='time', right_on='time_start', how='left')

    # Add tariff column by aligning hourly tariff series
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
    
    print(f'\nFetched {len(df_result)} hours of data from {from_date} to {to_date}\n')
    print(df_result.to_string(index=False))
    print(f'\nTotal usage: {df_result["usage_kwh"].sum():.2f} kWh')
    print(f'Total spot cost: {(df_result["usage_kwh"] * df_result["spot_pris"]).sum():.2f} DKK')
    print(f'Total tariff cost: {(df_result["usage_kwh"] * df_result["tarif_pris"]).sum():.2f} DKK')
    print(f'Total cost: {df_result["total_udgift"].sum():.2f} DKK')
    
    return df_result

if __name__ == '__main__':
    df = fetch_power_data()

