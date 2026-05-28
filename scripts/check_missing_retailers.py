"""Check a few specific retailers that had suspicious results."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
sb = get_supabase_client()

# Check Hy-Vee, Food Lion, Winn-Dixie
for rk in ("hyve", "hyvee", "hy_vee", "foodlion", "food_lion", "winndixie", "winn_dixie", "winco", "wincofoods"):
    res = sb.table("store_locations").select("count", count="exact").eq("retailer_key", rk).execute()
    print(f"  {rk}: {res.count} rows")

# Also check what's in store_locations for those display names
for name in ("Hy-Vee", "Hy Vee", "Food Lion", "Winn-Dixie", "WinCo Foods"):
    rk_search = name.lower().replace("-", "").replace(" ", "").replace("'", "").replace(".", "")
    res = sb.table("store_locations").select("count", count="exact").ilike("retailer", f"%{name.split('-')[0]}%").execute()
    print(f"  retailer LIKE '{name.split('-')[0]}%': {res.count} rows")
