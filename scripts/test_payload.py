# scripts/test_payload.py
# Test notification payload format without sending — shows exactly what
# would appear on the user's lock screen for each deal

import sys
sys.path.insert(0, '.')

deals = [
    {
        "product":    "cherry bomb energy drink",
        "retailer":   "Target",
        "best_price": 2.59,
        "savings_pct": 78.0,
        "trigger_type": "unchanged",
        "deal_reason": "target has cherry bomb energy drink for $2.59 — 78% below average across 4 retailers",
    },
    {
        "product":    "energy drink",
        "retailer":   "Walmart",
        "best_price": 2.57,
        "savings_pct": 88.0,
        "trigger_type": "unchanged",
        "deal_reason": "walmart has energy drink for $2.57 — 88% below average across 6 retailers",
    },
]

def build_title(retailer, savings_pct, trigger_type):
    retailer_display = retailer.title()
    if trigger_type == "drop":
        return f"Price drop at {retailer_display}!"
    elif savings_pct >= 50:
        return f"Big savings at {retailer_display}!"
    elif savings_pct >= 25:
        return f"Great deal at {retailer_display}!"
    else:
        return f"New deal at {retailer_display}"

def build_body(product, best_price, savings_pct, retailer_count=4):
    product_display = product.title()
    return f"{product_display} for ${best_price:.2f} — {savings_pct:.0f}% below average across {retailer_count} retailers near you."

print("\n── Notification Preview (Lock Screen Format) ────────────\n")
for deal in deals:
    title = build_title(deal["retailer"], deal["savings_pct"], deal["trigger_type"])
    body  = build_body(deal["product"], deal["best_price"], deal["savings_pct"])
    print(f"  ┌─────────────────────────────────────────┐")
    print(f"  │ prox                              now   │")
    print(f"  │ {title:<40}│")
    print(f"  │ {body[:40]:<40}│")
    if len(body) > 40:
        print(f"  │ {body[40:80]:<40}│")
    print(f"  └─────────────────────────────────────────┘")
    print()

print("  deep_link: /deals?source=new-deals-alert\n")