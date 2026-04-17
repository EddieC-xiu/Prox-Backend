import requests, json

url = "https://www.albertsons.com/abs/pub/xapi/storeresolver/v2/all"
headers = {
    "Ocp-Apim-Subscription-Key": "7bad9afbb87043b28519c4443106db06",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "referer": "https://www.albertsons.com/",
    "page-name": "fulfillment-modal",
}
params = {
    "zipcode": "90210",
    "size": 100,
    "radius": 200,
    "excludeBanners": "none",
    "includeNonMigratedStores": "true",
}

resp = requests.get(url, headers=headers, params=params, timeout=15)
print("Status:", resp.status_code)
data = resp.json()
print("\nTop-level keys:", list(data.keys()))

for key in data:
    val = data[key]
    if isinstance(val, list) and len(val) > 0:
        print(f"\nFound list under '{key}' with {len(val)} items")
        print("First item keys:", list(val[0].keys()))
        print(json.dumps(val[0], indent=2))
        break
    elif isinstance(val, dict):
        for subkey in val:
            subval = val[subkey]
            if isinstance(subval, list) and len(subval) > 0:
                print(f"\nFound list under '{key}.{subkey}' with {len(subval)} items")
                print("First item keys:", list(subval[0].keys()))
                print(json.dumps(subval[0], indent=2))
                break
