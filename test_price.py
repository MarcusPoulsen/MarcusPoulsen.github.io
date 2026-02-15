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
    print(f"Fetching electricity prices from {start_date} to {end_date} for zone {zone}...")
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

#debug test:
print('--- DEBUG: Fetching electricity prices for test ---'
      )
start_date = "2025-07-01"
end_date = "2026-01-31"
df_prices = fetch_el_price_range(start_date, end_date, zone='DK2')
print('--- DEBUG: Spot price data range ---')
print(df_prices.head(20))
print(df_prices.tail(20))