#!/usr/bin/env python3
"""Test script: print tariff price per hour for the last 5 days.

Reads refresh token from token.txt in repository root.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
import sys

TOKEN_FILE = 'token.txt'
API_BASE = 'https://api.eloverblik.dk/customerapi/api'

def load_refresh_token(path=TOKEN_FILE):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception as e:
        print('Could not read token.txt:', e)
        sys.exit(1)

def get_access_token(refresh):
    r = requests.get(f'{API_BASE}/token', headers={'Authorization': f'Bearer {refresh}'}, timeout=10)
    if r.status_code != 200:
        print('Token exchange failed:', r.status_code, r.text)
        sys.exit(1)
    return r.json().get('result')

def get_metering_points(access):
    r = requests.get(f'{API_BASE}/meteringpoints/meteringpoints', headers={'Authorization': f'Bearer {access}'}, timeout=10)
    if r.status_code != 200:
        print('Failed fetching metering points:', r.status_code, r.text)
        sys.exit(1)
    res = r.json().get('result') or []
    return [m.get('meteringPointId') for m in res if m.get('meteringPointId')]

def parse_iso_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

def fetch_charges(access, points):
    r = requests.post(f'{API_BASE}/meteringpoints/meteringpoint/getcharges', json={'meteringPoints': {'meteringPoint': points}}, headers={'Authorization': f'Bearer {access}'}, timeout=20)
    if r.status_code != 200:
        print('Failed fetching charges:', r.status_code, r.text)
        sys.exit(1)
    return r.json().get('result') or []

def build_hourly_tariffs(charges_result, start_dt, end_dt, tzname='Europe/Copenhagen'):
    tz = ZoneInfo(tzname)
    # build hourly timestamps
    start = start_dt.replace(minute=0, second=0, microsecond=0).astimezone(tz)
    end = end_dt.replace(minute=0, second=0, microsecond=0).astimezone(tz)
    hours = []
    cur = start
    while cur <= end:
        hours.append(cur)
        cur = cur + timedelta(hours=1)

    # initialize dict
    tariff_by_hour = {h: 0.0 for h in hours}

    for item in charges_result:
        result = item.get('result') or {}
        tariffs = result.get('tariffs') or []
        for tariff in tariffs:
            period_type = (tariff.get('periodType') or '').upper()
            vfrom = parse_iso_dt(tariff.get('validFromDate'))
            vto = parse_iso_dt(tariff.get('validToDate'))
            if vfrom is None:
                vfrom = start
            if vto is None:
                vto = end
            # normalize to tz
            try:
                vfrom = vfrom.astimezone(tz)
            except Exception:
                vfrom = vfrom.replace(tzinfo=timezone.utc).astimezone(tz)
            try:
                vto = vto.astimezone(tz)
            except Exception:
                vto = vto.replace(tzinfo=timezone.utc).astimezone(tz)

            # determine applicable hours
            for h in hours:
                if not (vfrom.replace(minute=0, second=0, microsecond=0) <= h <= vto.replace(minute=0, second=0, microsecond=0)):
                    continue
                if period_type == 'HOUR':
                    prices = tariff.get('prices') or []
                    for p in prices:
                        pos = p.get('position')
                        price = float(p.get('price') or 0)
                        try:
                            hour_of_day = (int(pos) - 1) % 24
                        except Exception:
                            continue
                        if h.hour == hour_of_day:
                            tariff_by_hour[h] += price
                else:
                    # DAY or other: apply first price to all hours
                    prices = tariff.get('prices') or []
                    price = 0.0
                    if prices:
                        price = float(prices[0].get('price') or 0)
                    tariff_by_hour[h] += price

    return tariff_by_hour

def main():
    refresh = load_refresh_token()
    access = get_access_token(refresh)
    points = get_metering_points(access)
    if not points:
        print('No metering points found')
        sys.exit(1)

    now = datetime.now(timezone.utc).astimezone(ZoneInfo('Europe/Copenhagen'))
    start = now - timedelta(days=5)

    charges = fetch_charges(access, points)
    tariffs = build_hourly_tariffs(charges, start, now)

    print('Timestamp, Tarif DKK/kWh')
    for ts in sorted(tariffs.keys()):
        print(f"{ts.isoformat()} , {tariffs[ts]:.6f}")

if __name__ == '__main__':
    main()
