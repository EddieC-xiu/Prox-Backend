import requests
import time
import sys
sys.path.insert(0, '.')
from config.supabase import get_supabase_client

sb = get_supabase_client()
headers = {'User-Agent': 'ProxApp/1.0 (grocery store locator)'}

# Smart & Final is mainly CA/Southwest — use smaller bounding boxes
REGIONS = [
    ("SoCal",      32, -119, 35, -114),
    ("NorCal",     35, -123, 38, -119),
    ("BayCal",     37, -123, 38.5, -121),
    ("Arizona",    31, -115, 37, -109),
    ("Nevada",     35, -120, 42, -114),
    ("Oregon",     42, -125, 47, -116),
]

url = 'https://overpass-api.de/api/interpreter'
all_stores = []

for region_name, south, west, north, east in REGIONS:
    query = f'[out:json][timeout:30];(node["name"~"Smart.*Final",i]({south},{west},{north},{east});way["name"~"Smart.*Final",i]({south},{west},{north},{east}););out center;'
    for attempt in range(3):
        try:
            res = requests.post(url, data={'data': query}, headers=headers, timeout=60)
            if res.status_code == 200:
                elements = res.json().get('elements', [])
                for e in elements:
                    lat = e.get('lat') or e.get('center', {}).get('lat')
                    lon = e.get('lon') or e.get('center', {}).get('lon')
                    name = e.get('tags', {}).get('name', 'Smart & Final')
                    if lat and lon:
                        all_stores.append({'lat': lat, 'lon': lon, 'name': name})
                print(f'{region_name}: {len(elements)} stores')
                break
            else:
                print(f'{region_name}: status {res.status_code}, retrying...')
        except Exception as e:
            print(f'{region_name} attempt {attempt+1}: {e}')
            time.sleep(10)
    time.sleep(3)

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

print(f'Total unique: {len(unique)}')
if unique:
    for i in range(0, len(unique), 500):
        sb.table('store_locations').upsert(unique[i:i+500]).execute()
        print(f'Inserted batch {i//500 + 1}')
print('Done.')