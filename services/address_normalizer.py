# services/address_normalizer.py
# Maps raw scraper retailer names to canonical retailer_key values.
# Add new entries to RETAILER_KEY_MAP as new scrapers are onboarded.

import re

RETAILER_KEY_MAP: dict[str, str] = {
    "kroger":               "kroger",
    "king soopers":         "kroger",
    "ralphs":               "kroger",
    "fred meyer":           "kroger",
    "smith's":              "kroger",
    "fry's":                "kroger",
    "publix":               "publix",
    "safeway":              "safeway",
    "albertsons":           "albertsons",
    "vons":                 "albertsons",
    "jewel":                "jewelosco",
    "jewel-osco":           "jewelosco",
    "acme":                 "acmemarkets",
    "tom thumb":            "tomthumb",
    "randalls":             "randalls",
    "shaw's":               "shaws",
    "shaws":                "shaws",
    "star market":          "starmarket",
    "haggen":               "haggen",
    "carrs":                "carrsqc",
    "balducci":             "balduccis",
    "kings food":           "kingsfoodmarkets",
    "market street":        "shopmarketstreet",
    "united supermarket":   "shopunitedsupermarkets",
    "smart & final":        "smart_and_final",
    "smart and final":      "smart_and_final",
    "walmart":              "walmart",
    "wal-mart":             "walmart",
    "target":               "target",
    "whole foods":          "whole_foods",
    "trader joe":           "trader_joes",
    "aldi":                 "aldi",
    "lidl":                 "lidl",
    "costco":               "costco",
    "sam's club":           "sams_club",
    "sams club":            "sams_club",
    "h-e-b":                "heb",
    "heb":                  "heb",
    "meijer":               "meijer",
    "stop & shop":          "stop_and_shop",
    "stop and shop":        "stop_and_shop",
    "giant":                "giant",
    "wegmans":              "wegmans",
    "harris teeter":        "harris_teeter",
    "food lion":            "food_lion",
    "sprouts":              "sprouts",
    "winn-dixie":           "winn_dixie",
    "winndixie":            "winn_dixie",
    "dollar general":       "dollar_general",
    "family dollar":        "family_dollar",
    "cvs":                  "cvs",
    "walgreens":            "walgreens",
    "rite aid":             "rite_aid",
}


def normalize_retailer_key(raw: str) -> str | None:
    """
    Map a raw scraper name to a canonical retailer_key.
    Returns None if no match found.

    Examples:
        "PUBLIX SUPER MARKETS #1234" → "publix"
        "Kroger #456"                → "kroger"
        "Jewel-Osco"                 → "jewelosco"
    """
    if not raw:
        return None
    lower = raw.lower().strip()
    for pattern, key in RETAILER_KEY_MAP.items():
        if pattern in lower:
            return key
    return None


def make_retailer_key(raw: str) -> str | None:
    """
    Fallback: slugify a raw name when no explicit mapping exists.
    Strips store numbers, punctuation, and common suffixes.

    Examples:
        "Fresh Market #789"  → "fresh_market"
        "ABC Grocery Store"  → "abc_grocery"
    """
    if not raw:
        return None
    s = raw.lower().strip()
    s = re.sub(r"#\s*\d+", "", s)
    for suffix in (" store", " supermarket", " super market", " market",
                   " grocery", " foods", " food", " pharmacy", " drug"):
        s = s.replace(suffix, "")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or None


def normalize_address(raw: str | None) -> str | None:
    """
    Lowercase and strip suite/unit noise for deduplication.
    """
    if not raw:
        return None
    s = raw.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\bste\.?\s*#?\d+\b", "", s)
    s = re.sub(r"\bunit\s*#?\d+\b", "", s)
    s = re.sub(r"\bsuite\s*#?\d+\b", "", s)
    return s.strip(", ").strip()

