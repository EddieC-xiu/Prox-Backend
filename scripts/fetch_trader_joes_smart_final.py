import requests
import time
import sys
sys.path.insert(0, '.')
from config.supabase import get_supabase_client

sb = get_supabase_client()
headers = {'User-Agent': 'ProxApp/1.0 (grocery store locator)'}

REGIONS = [
    ("Northeast", 38, -80, 47, -66),
    ("Southeast", 25, -92, 38, -75),
    ("Midwest",   36, -104, 49, -80),
    ("South",     25, -106, 36, -88),
    ("West",      32, -125, 49, -104),
    ("Southwest", 25, -117, 37, -104),
]

def fetch_region(brand, region_name, south, west, north, east):
    url = 'https://overpass-api.de/api/interpreter'
    # No shop filter — just search by name
    query = f'[out:json][timeout:60];(node["name"~"{brand}",i]({south},{west},{north},{east});way["name"~"{brand}",i]({south},{west},{north},{east}););out center;'
    try:
        res = requests.post(url, data={'data': query}, headers=headers, timeout=90)
        if res.status_code != 200:
            print(f'  {region_name}: status {res.status_code}')
            return []
        elements = res.json().get('elements', [])
        stores = []
        for e in elements:
            lat = e.get('lat') or e.get('center', {}).get('lat')
            lon = e.get('lon') or e.get('center', {}).get('lon')
            name = e.get('tags', {}).get('name', brand)
            if lat and lon:
                stores.append({'lat': lat, 'lon': lon, 'name': name})
        print(f'  {region_name}: {len(stores)} stores')
        return stores
    except Exception as e:
        print(f'  {region_name}: error {e}')
        return []

def fetch_and_insert(brand, retailer_key):
    print(f'\nFetching {retailer_key}...')
    all_stores = []
    for region_name, south, west, north, east in REGIONS:
        stores = fetch_region(brand, region_name, south, west, north, east)
        all_stores.extend(stores)
        time.sleep(5)

    seen = set()
    unique = []
    for s in all_stores:
        key = (round(s['lat'], 4), round(s['lon'], 4))
        if key not in seen:
            seen.add(key)
            unique.append({
                'retailer': s['name'],
                'retailer_key': retailer_key,
                'latitude': s['lat'],
                'longitude': s['lon'],
                'show_on_map': True
            })

    print(f'Total unique {retailer_key}: {len(unique)}')
    if unique:
        for i in range(0, len(unique), 500):
            sb.table('store_locations').upsert(unique[i:i+500]).execute()
            print(f'  Inserted batch {i//500 + 1}')
    return len(unique)

tj_count = fetch_and_insert("Trader Joe", "trader_joes")
time.sleep(10)
sf_count = fetch_and_insert("Smart Final", "smart_final")
print(f"\nDone. Trader Joes: {tj_count}, Smart Final: {sf_count}")

# Add to bottom of script, replace sf_count line
def fetch_smart_final():
    print('\nFetching smart_final...')
    url = 'https://overpass-api.de/api/interpreter'
    all_stores = []
    for region_name, south, west, north, east in REGIONS:
        query = f'[out:json][timeout:60];(node["name"~"Smart",i]["name"~"Final",i]({south},{west},{north},{east});way["name"~"Smart",i]["name"~"Final",i]({south},{west},{north},{east}););out center;'
        try:
            res = requests.post(url, data={'data': query}, headers=headers, timeout=90)
            if res.status_code == 200:
                elements = res.json().get('elements', [])
                for e in elements:
                    lat = e.get('lat') or e.get('center', {}).get('lat')
                    lon = e.get('lon') or e.get('center', {}).get('lon')
                    name = e.get('tags', {}).get('name', 'Smart & Final')
                    if lat and lon:
                        all_stores.append({'lat': lat, 'lon': lon, 'name': name})
                print(f'  {region_name}: {len(elements)} stores')
            time.sleep(5)
        except Exception as e:
            print(f'  {region_name}: error {e}')

    seen = set()
    unique = []
    for s in all_stores:
        key = (round(s['lat'], 4), round(s['lon'], 4))
        if key not in seen:
            seen.add(key)
            unique.append({
                'retailer': s['name'],
                'retailer_key': 'smart_final',
                'latitude': s['lat'],
                'longitude': s['lon'],
                'show_on_map': True
            })

    print(f'Total unique smart_final: {len(unique)}')
    if unique:
        for i in range(0, len(unique), 500):
            sb.table('store_locations').upsert(unique[i:i+500]).execute()
            print(f'  Inserted batch {i//500 + 1}')
    return len(unique)

sf_count = fetch_smart_final()
print(f'Smart Final: {sf_count}')