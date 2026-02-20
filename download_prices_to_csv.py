#!/usr/bin/env python3
import pandas as pd
from datetime import datetime, timedelta
from fetch_power_data import fetch_el_price_range

# Define periods to download
periods = [
    ("2024-01-01", "2025-12-31"),
    ("2026-01-01", "2026-01-31")
]

all_prices = []
for start, end in periods:
    print(f"Fetching prices from {start} to {end}...")
    df = fetch_el_price_range(start, end, zone="DK2")
    if not df.empty:
        # Add moms (25%) to spot price
        if 'DKK_per_kWh' in df.columns:
            df['DKK_per_kWh'] = df['DKK_per_kWh'] * 1.25
        all_prices.append(df)
    else:
        print(f"No prices found for {start} to {end}")

if all_prices:
    df_all = pd.concat(all_prices, ignore_index=True)
    df_all.to_csv("historic_el_prices.csv", index=False)
    print("Saved prices to historic_el_prices.csv")
else:
    print("No price data to save.")
