import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timezone
import requests
import time
import csv

try:
    import pgeocode
    PGEOCODE_AVAILABLE = True
except ImportError:
    PGEOCODE_AVAILABLE = False
    print("Warning: pgeocode not installed. Using fallback state centroids.")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

US_LAT_MIN, US_LAT_MAX = 18.0, 72.0
US_LON_MIN, US_LON_MAX = -180.0, -60.0

def valid_us_coords(lat, lon):
    try:
        return (US_LAT_MIN <= float(lat) <= US_LAT_MAX and
                US_LON_MIN <= float(lon) <= US_LON_MAX)
    except (TypeError, ValueError):
        return False

SNF_ZIPS = [
    # Los Angeles Basin
    "90001","90011","90021","90031","90041","90051","90061","90071",
    "90201","90210","90220","90230","90240","90250","90260","90270",
    "90280","90290","90301","90401","90501","90601","90701","90801",
    "91001","91010","91020","91030","91040","91101","91201","91301",
    "91401","91501","91601","91701","91801","91901",
    "92801","92831","92861","92868","92870","92886",
    # San Diego
    "92101","92103","92104","92105","92108","92110","92111","92114",
    "92115","92116","92120","92123","92126","92131","92139","92154",
    "92037","92057","92065","92071","92081","92083","92084",
    # Inland Empire
    "92201","92220","92223","92301","92316","92324","92335","92336",
    "92337","92345","92346","92352","92354","92373","92374","92376",
    "92395","92399","92401","92404","92408","92410","92501","92503",
    "92504","92505","92506","92507","92508","92509","92530","92544",
    "92545","92553","92557","92562","92563","92571","92582","92583",
    "92584","92585","92586","92587",
    # San Fernando / Ventura
    "91302","91303","91304","91306","91307","91311","91316","91324",
    "91325","91326","91331","91335","91340","91342","91343","91344",
    "91345","91350","91351","91352","91354","91355","91356","91360",
    "91361","91362","91364","91367","91381","91384","91387","91390",
    "93010","93012","93021","93030","93033","93035","93036","93040",
    "93041","93060","93063","93065",
    # Central Valley
    "93201","93210","93215","93230","93240","93245","93247","93250",
    "93251","93257","93261","93263","93265","93268","93270","93272",
    "93274","93277","93278","93280","93285","93286","93291","93292",
    "93301","93304","93305","93306","93307","93308","93309","93311",
    "93312","93313","93314","93401","93420","93422","93428","93432",
    "93433","93436","93437","93440","93441","93442","93444","93446",
    "93449","93450","93451","93452","93453","93454","93455","93458",
    "93460","93461","93463","93465",
    # Bay Area
    "94002","94010","94014","94015","94019","94025","94027","94030",
    "94040","94041","94043","94044","94061","94062","94063","94065",
    "94066","94080","94102","94103","94107","94109","94110","94112",
    "94114","94116","94117","94118","94122","94124","94127","94131",
    "94132","94134","94401","94403","94404","94501","94502","94503",
    "94509","94510","94513","94514","94516","94518","94519","94520",
    "94521","94523","94525","94530","94531","94533","94534","94535",
    "94536","94538","94539","94541","94542","94544","94545","94546",
    "94547","94548","94549","94550","94551","94553","94555","94556",
    "94558","94559","94560","94561","94563","94564","94565","94566",
    "94568","94572","94575","94577","94578","94579","94580","94582",
    "94583","94585","94586","94587","94588","94589","94590","94591",
    "94592","94595","94597","94598","94601","94602","94603","94605",
    "94606","94607","94608","94609","94610","94611","94612","94619",
    "94621","94702","94703","94704","94705","94706","94707","94708",
    "94709","94710","94720","94801","94803","94804","94805","94806",
    "94901","94903","94904","94920","94930","94939","94941","94945",
    "94947","94949","94952","94954","94960","94965",
    # Sacramento
    "95610","95621","95624","95626","95628","95630","95632","95638",
    "95640","95648","95650","95655","95660","95662","95670","95673",
    "95677","95678","95682","95683","95691","95693","95742","95747",
    "95758","95762","95765","95811","95814","95815","95816","95817",
    "95818","95819","95820","95821","95822","95823","95824","95825",
    "95826","95827","95828","95829","95831","95832","95833","95834",
    "95835","95838","95841","95842","95843","95864",
    # Fresno
    "93650","93701","93702","93703","93704","93705","93706","93710",
    "93711","93720","93721","93722","93723","93725","93726","93727",
    "93728","93730","93740","93741",
    # Nevada
    "89002","89005","89011","89012","89014","89015","89030","89031",
    "89032","89044","89046","89048","89052","89074","89081","89084",
    "89086","89101","89102","89103","89104","89106","89107","89108",
    "89109","89110","89113","89115","89117","89118","89119","89120",
    "89121","89122","89123","89124","89128","89129","89130","89131",
    "89134","89135","89138","89139","89141","89142","89143","89144",
    "89145","89146","89147","89148","89149","89156","89161","89166",
    "89169","89178","89183","89191","89193","89431","89434","89436",
    "89441","89501","89502","89503","89505","89506","89509","89511",
    "89512","89519","89521","89523","89557","89701","89703","89705",
    # Arizona
    "85003","85004","85006","85007","85008","85009","85012","85013",
    "85014","85015","85016","85017","85018","85019","85020","85021",
    "85022","85023","85024","85027","85028","85029","85031","85032",
    "85033","85034","85035","85037","85040","85041","85042","85043",
    "85044","85045","85048","85050","85051","85053","85054","85083",
    "85085","85086","85087","85201","85202","85203","85204","85205",
    "85206","85207","85208","85209","85210","85212","85213","85215",
    "85224","85225","85226","85233","85234","85248","85249","85251",
    "85253","85254","85255","85256","85257","85258","85259","85260",
    "85262","85266","85268","85281","85282","85283","85284","85286",
    "85295","85296","85297","85298","85299","85301","85302","85303",
    "85304","85305","85306","85308","85309","85310","85323","85326",
    "85331","85335","85338","85339","85340","85342","85344","85345",
    "85351","85353","85354","85355","85363","85373","85374","85375",
    "85376","85379","85381","85382","85383","85387","85388","85395",
    "85396","85501","85541","85543","85546","85601","85614","85621",
    "85629","85631","85635","85641","85643","85645","85648","85650",
    "85701","85705","85706","85707","85708","85710","85711","85712",
    "85713","85714","85715","85716","85718","85719","85730","85741",
    "85743","85745","85746","85747","85748","85749","85750","85756",
    "85757","86001","86004","86011","86021","86022","86023","86025",
    "86040","86044","86045","86046","86047","86401","86403","86404",
    "86406","86409","86413","86426","86429","86431","86432","86433",
    "86434","86436","86438","86440","86441","86442","86443","86444",
    "86445","86446","86502","86503","86504","86505","86506","86507",
    "86508","86510","86511","86512","86514","86515","86520",
]

_nomi = None

def get_zip_coords(zip_code):
    global _nomi
    STATE_CENTROIDS = {
        "CA": (36.7783, -119.4179),
        "NV": (38.8026, -116.4194),
        "AZ": (34.0489, -111.0937),
    }
    if PGEOCODE_AVAILABLE:
        if _nomi is None:
            _nomi = pgeocode.Nominatim("us")
        result = _nomi.query_postal_code(zip_code)
        if result is not None and not (result.latitude != result.latitude):
            return float(result.latitude), float(result.longitude)
    z = int(zip_code)
    if 89000 <= z <= 89999:
        return STATE_CENTROIDS["NV"]
    if 85000 <= z <= 86999:
        return STATE_CENTROIDS["AZ"]
    return STATE_CENTROIDS["CA"]

BASE_URL = ("https://storefrontgateway.smartandfinal.com/api/v1"
            "/code/{zip}/ShoppingModes"
            "/22222222-2222-2222-2222-222222222222/Stores")

def fetch_snf_stores(zip_code, lat, lon, debug=False):
    url = BASE_URL.format(zip=zip_code)
    headers = {
        "accept":                       "application/json, text/plain, */*",
        "origin":                       "https://www.smartandfinal.com",
        "referer":                      "https://www.smartandfinal.com/",
        "x-customer-address-latitude":  str(lat),
        "x-customer-address-longitude": str(lon),
        "x-shopping-mode":              "22222222-2222-2222-2222-222222222222",
        "x-site-host":                  "https://www.smartandfinal.com",
        "User-Agent":                   "Mozilla/5.0",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if debug:
            print(f"\n[DEBUG ZIP {zip_code}] STATUS: {resp.status_code}")
            print(resp.text[:2000])
        if resp.status_code == 200:
            data = resp.json()
            # Response shape: {"total": N, "items": [...]}
            items = data.get("items") or data.get("stores") or []
            return items, resp.status_code
        return [], resp.status_code
    except Exception as e:
        return [], str(e)

def parse_snf_store(store):
    store_id = str(store.get("retailerStoreId") or store.get("storeId") or "").strip()
    if not store_id:
        return None

    # Coords are nested under "location"
    loc = store.get("location") or {}
    lat = store.get("latitude") or store.get("lat") or loc.get("latitude")
    lon = store.get("longitude") or store.get("lng") or store.get("lon") or loc.get("longitude")

    if not lat or not lon or not valid_us_coords(lat, lon):
        return None

    street  = (store.get("addressLine1") or store.get("address1") or "").strip()
    city    = (store.get("city") or "").strip()
    state   = (store.get("countyProvinceState") or store.get("state") or "").strip()
    zip_out = (store.get("postCode") or store.get("zipCode") or store.get("zip") or "").strip()[:5]
    phone   = (store.get("phone") or store.get("phoneNumber") or "").strip()
    name    = (store.get("name") or store.get("storeName") or "Smart & Final").strip()

    full_address = ", ".join(filter(None, [
        street, city,
        f"{state} {zip_out}".strip() if state else zip_out,
    ]))

    return {
        "retailer":           "Smart & Final",
        "retailer_key":       "smart_and_final",
        "store_id":           store_id,
        "address":            street or None,
        "full_address":       full_address or None,
        "zip_code":           zip_out or None,
        "latitude":           float(lat),
        "longitude":          float(lon),
        "geocode_confidence": "high",
        "geocode_source":     "api",
        "geocoded_at":        datetime.now(timezone.utc).isoformat(),
        "_phone":             phone or None,
        "_name":              name,
    }

def scrape_snf_stores(export_csv=True, dry_run=False):
    supabase = None if dry_run else create_client(SUPABASE_URL, SUPABASE_KEY)

    zip_list = sorted(set(SNF_ZIPS))
    total    = len(zip_list)
    print(f"Smart & Final scraper starting — {total} ZIP codes to search...\n")

    seen: dict[str, dict] = {}
    api_errors = 0
    first_zip  = True

    for i, zip_code in enumerate(zip_list, 1):
        lat, lon = get_zip_coords(zip_code)
        raw, status = fetch_snf_stores(zip_code, lat, lon, debug=first_zip)
        first_zip = False

        if not isinstance(raw, list):
            api_errors += 1
        else:
            for store in raw:
                record = parse_snf_store(store)
                if record:
                    seen[record["store_id"]] = record

        if i % 50 == 0 or i == total:
            print(f"  [{i:>4}/{total}] zips done — {len(seen)} unique stores found")

        time.sleep(0.2)

    print(f"\nTotal unique stores found: {len(seen)}")
    print(f"API errors: {api_errors}")

    if not seen:
        print("\n⚠  No stores found. Check DEBUG output above.")
        return

    records = list(seen.values())

    from collections import Counter
    state_counts = Counter()
    for r in records:
        z = int(r.get("zip_code") or 0)
        if 89000 <= z <= 89999:
            state_counts["NV"] += 1
        elif 85000 <= z <= 86999:
            state_counts["AZ"] += 1
        else:
            state_counts["CA"] += 1
    print("\nStores by state:")
    for state, count in sorted(state_counts.items()):
        print(f"  {state}: {count}")

    if export_csv:
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = os.path.join(os.path.dirname(__file__), "../data")
        os.makedirs(data_dir, exist_ok=True)
        csv_path = os.path.join(data_dir, f"smart_and_final_stores_{ts}.csv")
        fieldnames = ["retailer","retailer_key","store_id","_name","address",
                      "full_address","zip_code","latitude","longitude",
                      "_phone","geocode_confidence","geocode_source","geocoded_at"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        print(f"\nCSV saved → {csv_path}")

    if dry_run:
        print("\nDry-run mode — skipping DB writes.")
        return

    db_fields = ["retailer","retailer_key","store_id","address","full_address",
                 "zip_code","latitude","longitude","geocode_confidence",
                 "geocode_source","geocoded_at"]

    print("\nWriting to Supabase...")
    inserted = updated = db_errors = 0

    for record in records:
        db_record = {k: v for k, v in record.items() if k in db_fields}
        try:
            existing = (supabase.table("store_locations").select("id")
                        .eq("retailer_key", "smart_and_final")
                        .eq("store_id", db_record["store_id"]).execute())
            if existing.data:
                supabase.table("store_locations").update(db_record)\
                    .eq("id", existing.data[0]["id"]).execute()
                updated += 1
            else:
                supabase.table("store_locations").insert(db_record).execute()
                inserted += 1
        except Exception as e:
            print(f"  DB error store {db_record['store_id']}: {e}")
            db_errors += 1

    print(f"\n{'='*45}")
    print(f"  Smart & Final Import Complete")
    print(f"  Stores found  : {len(records)}")
    print(f"  Inserted      : {inserted}")
    print(f"  Updated       : {updated}")
    print(f"  DB errors     : {db_errors}")
    print(f"{'='*45}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Scrape and export CSV without writing to DB")
    parser.add_argument("--no-csv", action="store_true",
                        help="Skip CSV export")
    args = parser.parse_args()
    scrape_snf_stores(export_csv=not args.no_csv, dry_run=args.dry_run)