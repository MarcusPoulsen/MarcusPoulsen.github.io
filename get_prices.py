import requests
import pandas as pd
from datetime import datetime, timedelta

#https://www.elprisenligenu.dk/elpris-api

def fetch_el_price_range(start_date: str, end_date: str, zone: str = "DK2") -> pd.DataFrame:
    """
    Fetches electricity prices from Elprisenligenu API for a range of dates.

    Parameters:
        start_date (str): Format 'YYYY-MM-DD'
        end_date (str): Format 'YYYY-MM-DD'
        zone (str): 'DK1' or 'DK2'

    Returns:
        pd.DataFrame: Combined data with 'time_start' and 'DKK_per_kWh'
    """
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
            
    return pd.concat(all_data, ignore_index=True)



