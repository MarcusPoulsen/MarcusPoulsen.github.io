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
            df['time_start'] = pd.to_datetime(df['time_start'], utc=True)
            all_data.append(df)
        except Exception as e:
            print(f"Failed for {date_str}: {e}")
            
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

def fetch_tariff_data(access_token: str, points: list, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.Series:
    """Load manual tariff CSV (`tariffs_manual.csv`) and build hourly series.

    CSV columns: month_start,month_end,hour_start,hour_end,price
    month ranges may wrap (e.g. 10 to 3).
    """
    # Ensure start_ts and end_ts are in Europe/Copenhagen, then strip tzinfo before passing to pd.date_range with explicit tz
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize('Europe/Copenhagen')
    else:
        start_ts = start_ts.tz_convert('Europe/Copenhagen')
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize('Europe/Copenhagen')
    else:
        end_ts = end_ts.tz_convert('Europe/Copenhagen')
    # Remove tzinfo before passing to pd.date_range with tz argument
    idx = pd.date_range(start=start_ts.floor('h').replace(tzinfo=None), end=end_ts.floor('h').replace(tzinfo=None), freq='h', tz=ZoneInfo('Europe/Copenhagen'))
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

    # --- DEBUG: Show all rows of usage and price data before join ---
    # (df_prices is not available yet, so only print df_power here)
    print("\n--- DEBUG: df_power (usage) ---")
    print(df_power.head(100))
    
    # Ensure both are timezone-aware and floored to hour in Europe/Copenhagen, then create naive local time for join
    df_power['time'] = pd.to_datetime(df_power['time'])
    # Remove all data for the DST transition hour (last Sunday of October, 02:00-02:59) for any year
    def is_last_sunday_of_oct(dt):
        # Accepts both pd.Timestamp and datetime
        if hasattr(dt, 'month') and hasattr(dt, 'weekday'):
            if dt.month == 10 and dt.weekday() == 6 and dt.day >= 25:
                # Find last Sunday of October for this year
                last_oct = datetime(dt.year, 10, 31)
                last_sunday = last_oct - timedelta(days=(last_oct.weekday() - 6) % 7)
                return dt.day == last_sunday.day
        return False
    # Remove all ambiguous times (DST transitions) for any year
    print('now filtering out DST transition hours from power data...')
    if df_power['time'].dt.tz is None:
        print('debug: power data is naive, localizing to Europe/Copenhagen with ambiguous=NaT to drop DST transition hours')
        df_power['time'] = pd.to_datetime(df_power['time'], errors='coerce')
        df_power['time'] = df_power['time'].dt.tz_localize('Europe/Copenhagen', ambiguous='NaT')
        df_power = df_power.dropna(subset=['time'])
    else:
        print('debug: power data is timezone-aware, converting to Europe/Copenhagen and filtering out DST transition hours')
        df_power['time'] = df_power['time'].dt.tz_convert('Europe/Copenhagen')
        print('went fine so far, now filtering out DST transition hours...')
    #df_power['time'] = df_power['time'].dt.floor('h')
    print('got to here, now applying filter for last Sunday of October 02:00-02:59...')
    df_power['time_local'] = df_power['time'].dt.tz_localize(None)

    # Fetch prices
    print('Fetching electricity prices...')
    df_prices = fetch_el_price_range(str(from_date), str(to_date), zone='DK2')
    if not df_prices.empty:
        # Add moms (25%) to spot price
        if 'DKK_per_kWh' in df_prices.columns:
            df_prices['DKK_per_kWh'] = df_prices['DKK_per_kWh'] * 1
        # Shift price interval forward by 1 hour only in wintertime (CET, UTC+1)
        # In summertime (CEST, UTC+2), do not shift
        def shift_if_winter(ts):
            # Europe/Copenhagen: UTC+1 is winter, UTC+2 is summer
            if ts.tzinfo is not None and ts.utcoffset() == timedelta(hours=1):
                return ts + pd.Timedelta(hours=1)
            return ts
        df_prices['time_start'] = df_prices['time_start'].apply(shift_if_winter)
        # Coerce errors to NaT to avoid ValueError on bad data
        print("\n--- DEBUG: df_prices (price) before NaT ---")
        with pd.option_context('display.max_rows', 100, 'display.max_columns', None):
            print(df_prices.head(100))
        df_prices['time_start'] = pd.to_datetime(df_prices['time_start'], errors='coerce')
        df_prices['time_start'] = pd.to_datetime(df_prices['time_start'], errors='coerce', utc=True)
        # Remove all data for the DST transition hour (last Sunday of October, 02:00-02:59) for any year
        # Remove all ambiguous times (DST transitions) for any year
        if df_prices['time_start'].dt.tz is None:
            df_prices['time_start'] = pd.to_datetime(df_prices['time_start'], errors='coerce')
            df_prices['time_start'] = df_prices['time_start'].dt.tz_localize('Europe/Copenhagen', ambiguous='NaT')
            df_prices = df_prices.dropna(subset=['time_start'])
        else:
            df_prices['time_start'] = df_prices['time_start'].dt.tz_convert('Europe/Copenhagen')
        #df_prices['time_start'] = df_prices['time_start'].dt.floor('h')
        df_prices['time_local'] = df_prices['time_start'].dt.tz_localize(None)
    else:
        print('Warning: Could not fetch price data')
        return df_power
    print("\n--- DEBUG: df_prices (price) ---")
    with pd.option_context('display.max_rows', 100, 'display.max_columns', None):
            print(df_prices.head(100))
    
    # Fetch tariff prices (build hourly series)
    print('Fetching tariff prices...')
    start_ts = df_power['time'].min()
    end_ts = df_power['time'].max()
    tariff_series = fetch_tariff_data(access, points, start_ts, end_ts)

    # Ensure both merge columns are datetime
    df_power['time'] = pd.to_datetime(df_power['time'])
    df_power['time'] = pd.to_datetime(df_power['time'], utc=True)
    try:
        df_prices['time_start'] = pd.to_datetime(df_prices['time_start'])
        df_prices['time_start'] = pd.to_datetime(df_prices['time_start'], utc=True)
    except Exception as e:
        print('Error converting df_prices["time_start"] to datetime:', e)
        print('Problematic values:', df_prices['time_start'].head(10).to_list())
        df_prices['time_start'] = pd.to_datetime(df_prices['time_start'], errors='coerce')
        df_prices['time_start'] = pd.to_datetime(df_prices['time_start'], errors='coerce', utc=True)
    # Merge power data with prices using naive local time to guarantee a match for every hour
    print("\n--- DEBUG: Merging on 'time_local' ---")
    df_merged = pd.merge(df_power, df_prices, left_on='time_local', right_on='time_local', how='left', suffixes=('', '_price'))
    # After merge, drop time_local columns and keep time in Europe/Copenhagen
    df_merged = df_merged.drop(columns=['time_local'])
    if 'time_local_price' in df_merged.columns:
        df_merged = df_merged.drop(columns=['time_local_price'])

    # Add tariff column by aligning hourly tariff series
    try:
        tariff_series = tariff_series.tz_convert(ZoneInfo('Europe/Copenhagen'))
    except Exception:
        pass
    df_merged = df_merged.sort_values('time')
    df_merged['tariff_dkk_per_kwh'] = tariff_series.reindex(pd.DatetimeIndex(df_merged['time'])).fillna(0).values
    # Load `afgift` (tax) per kWh from a CSV file if available, otherwise fall back to hardcoded defaults.
    afgift_series = pd.Series(0.0, index=tariff_series.index)
    try:
        afg = pd.read_csv('afgift_manual.csv')
        for _, row in afg.iterrows():
            ys = int(row['year_start'])
            ye = int(row['year_end'])
            val = float(row['afgift_dkk_per_kwh'])
            mask = (afgift_series.index.year >= ys) & (afgift_series.index.year <= ye)
            afgift_series.loc[mask] = val
    except Exception as e:
        # Fallback to previous behavior if CSV missing or malformed
        afgift_series.loc[[ts for ts in tariff_series.index if ts.year <= 2025]] = 0.9
        afgift_series.loc[[ts for ts in tariff_series.index if ts.year >= 2026]] = 0.01

    df_merged['afgift_dkk_per_kwh'] = afgift_series.reindex(pd.DatetimeIndex(df_merged['time'])).fillna(0).values

    # Calculate costs
    df_merged['spot_cost_dkk'] = df_merged['usage_kwh'] * df_merged['DKK_per_kWh']
    df_merged['tariff_cost_dkk'] = df_merged['usage_kwh'] * df_merged['tariff_dkk_per_kwh']
    df_merged['afgift_cost_dkk'] = df_merged['usage_kwh'] * df_merged['afgift_dkk_per_kwh']
    df_merged['total_cost_dkk'] = df_merged['spot_cost_dkk'] + df_merged['tariff_cost_dkk'] + df_merged['afgift_cost_dkk']
    
    # Select and order columns
    df_result = df_merged[['time', 'usage_kwh', 'DKK_per_kWh', 'tariff_dkk_per_kwh', 'afgift_dkk_per_kwh', 'total_cost_dkk']].copy()
    df_result.columns = ['time', 'usage_kwh', 'spot_pris', 'tarif_pris', 'afgift_pris', 'total_udgift']
    df_result = df_result.sort_values('time').reset_index(drop=True)
    # Detect car charging and allocate kWh based on thresholds provided
    try:
        df_result['car_charging'] = df_result['usage_kwh'] >= float(charge_threshold)
        df_result['car_kwh'] = 0.0
        mask = df_result['car_charging']
        if mask.any():
            df_result.loc[mask, 'car_kwh'] = df_result.loc[mask, 'usage_kwh'].clip(upper=float(car_max_kwh))
        df_result['house_kwh'] = df_result['usage_kwh'] - df_result['car_kwh']
    except Exception:
        # Fallback: ensure columns exist
        if 'car_kwh' not in df_result.columns:
            df_result['car_kwh'] = 0.0
        if 'car_charging' not in df_result.columns:
            df_result['car_charging'] = False
        if 'house_kwh' not in df_result.columns:
            df_result['house_kwh'] = df_result['usage_kwh']

    print(f'\nFetched {len(df_result)} hours of data from {from_date} to {to_date}\n')
    print(df_result.to_string(index=False))
    total_usage = df_result['usage_kwh'].sum()
    total_spot = (df_result['usage_kwh'] * df_result['spot_pris']).sum()
    total_tarif = (df_result['usage_kwh'] * df_result['tarif_pris']).sum()
    total_afgift = (df_result['usage_kwh'] * df_result['afgift_pris']).sum()
    total_cost = df_result['total_udgift'].sum()

    print(f'\nTotal usage: {total_usage:.2f} kWh')
    print(f'Total spot cost: {total_spot:.2f} DKK')
    print(f'Total tariff cost: {total_tarif:.2f} DKK')
    print(f'Total afgift (tax): {total_afgift:.2f} DKK')
    print(f'Total cost (spot + tariff + afgift): {total_cost:.2f} DKK')

    return df_result

if __name__ == '__main__':
    df = fetch_power_data()

