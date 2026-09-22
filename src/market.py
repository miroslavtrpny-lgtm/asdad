"""Rough market-comparison estimate for a new listing.

This is NOT a real valuation model like Valuo (which uses actual cadastre
sale prices) - it compares the listing's asking price against OTHER
CURRENTLY LISTED asking prices for the same disposition in the same
district on Sreality (the largest, most liquid source we have). It is a
"how does this compare to other offers nearby right now" signal, not a
"what is this really worth" signal - small districts can have very few
comparables, which makes the estimate weak or unavailable.
"""
import re
import statistics
import time
import unicodedata

import requests

from . import sreality

MIN_COMPS = 3
MAX_COMP_PAGES = 6

_OKRES_RE = re.compile(r"okres\s+([^,]+)", re.IGNORECASE)
_PRAHA_DISTRICT_RE = re.compile(r"\bpraha[\s-]*(\d{1,2})\b", re.IGNORECASE)
_RENT_IN_DESCRIPTION_RE = re.compile(
    r"(?:n[aá]jem(?:n[eé])?|pron[aá]jem)[^.\n]{0,25}?([\d][\d\s]{2,6})\s*K[cč]",
    re.IGNORECASE,
)


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return ascii_text


def _locality_slug(listing: dict):
    address = listing.get("address") or ""
    # Praha je príliš veľká na to, aby "praha" ako celok dávalo zmysluplné
    # porovnanie cien - ak vieme číslo mestskej časti, zúžime na tú.
    praha_match = _PRAHA_DISTRICT_RE.search(address)
    if praha_match:
        return f"praha-{praha_match.group(1)}"
    city = listing.get("city")
    if city:
        return _slugify(city)
    okres_match = _OKRES_RE.search(address)
    if okres_match:
        return _slugify(okres_match.group(1))
    if re.search(r"\bpraha\b", address, re.IGNORECASE):
        return "praha"
    first_part = address.split(",")[0].split(" - ")[0].strip()
    return _slugify(first_part) if first_part else None


def _fetch_district_results(slug: str, offer_type_path: str, max_pages: int = MAX_COMP_PAGES, delay: float = 0.5):
    results = []
    for page in range(1, max_pages + 1):
        params = {"strana": page} if page > 1 else {}
        url = f"{sreality.BASE_URL}/hledani/{offer_type_path}/byty/{slug}"
        resp = requests.get(url, params=params, headers=sreality.HEADERS, timeout=20)
        if resp.status_code != 200:
            break
        data = sreality._extract_next_data(resp.text)
        if not data:
            break
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        search_q = next((q for q in queries if q["queryKey"][0] == "estatesSearch"), None)
        if not search_q:
            break
        result_data = search_q["state"]["data"]
        page_results = result_data.get("results", [])
        if not page_results:
            break
        results.extend(page_results)
        pagination = result_data.get("pagination", {})
        if pagination.get("offset", 0) + len(page_results) >= pagination.get("total", 0):
            break
        time.sleep(delay)
    return results


def estimate_value(listing: dict):
    """Compares listing['price'] (+ optional surface_m2) against comparable
    sale listings (same dispozice, same district) currently on Sreality.
    Returns None when there's no usable locality or too few comps."""
    slug = _locality_slug(listing)
    dispozice = listing.get("dispozice")
    if not slug or not dispozice or dispozice == "neuvedené":
        return None
    try:
        sale_results = _fetch_district_results(slug, "prodej")
    except Exception:
        return None

    comps = [
        r["priceCzkPerSqM"]
        for r in sale_results
        if (r.get("categorySubCb") or {}).get("name") == dispozice and r.get("priceCzkPerSqM")
    ]
    if len(comps) < MIN_COMPS:
        return None

    median_price_per_m2 = statistics.median(comps)
    surface_m2 = listing.get("surface_m2")
    estimated_value = round(median_price_per_m2 * surface_m2 / 1000) * 1000 if surface_m2 else None

    asking_price = listing["price"]
    if estimated_value:
        ratio = asking_price / estimated_value
    elif surface_m2:
        ratio = None
    else:
        # bez plochy nevieme prepočítať na Kč, porovnáme aspoň Kč/m2 nepriamo
        ratio = None

    # Okresný medián je dosť hrubý (v jednom okrese býva aj drahšia aj lacnejšia
    # obec), takže prahy sú zámerne široké - cieľ je chytiť len jasné výchylky,
    # nie tváriť sa na presnosť, ktorú tento odhad nemá.
    if ratio is not None:
        if ratio <= 0.7:
            verdict = "pravdepodobne dobrá kúpa (výrazne pod odhadom okolia)"
        elif ratio >= 1.3:
            verdict = "pravdepodobne predražené (výrazne nad odhadom okolia)"
        else:
            verdict = "približne zodpovedá okoliu"
    else:
        verdict = "neuvedené (chýba plocha bytu na prepočet)"

    return {
        "comps_count": len(comps),
        "median_price_per_m2": round(median_price_per_m2),
        "estimated_value": estimated_value,
        "verdict": verdict,
    }


def estimate_rent(listing: dict, description: str = ""):
    """Either extracts an explicitly stated current rent from the
    description, or falls back to a rent range from comparable rental
    listings (same dispozice, same district) currently on Sreality."""
    match = _RENT_IN_DESCRIPTION_RE.search(description or "")
    if match:
        amount = int(re.sub(r"\s", "", match.group(1)))
        if 1000 <= amount <= 100_000:
            return {"source": "z popisu inzerátu", "value": amount}

    slug = _locality_slug(listing)
    dispozice = listing.get("dispozice")
    if not slug or not dispozice or dispozice == "neuvedené":
        return None
    try:
        rent_results = _fetch_district_results(slug, "pronajem")
    except Exception:
        return None

    comps = sorted(
        r["priceCzk"]
        for r in rent_results
        if (r.get("categorySubCb") or {}).get("name") == dispozice and r.get("priceCzk")
    )
    if len(comps) < MIN_COMPS:
        return None

    low = comps[len(comps) // 4]
    high = comps[(len(comps) * 3) // 4]
    if low == high and len(comps) >= 1:
        high = comps[-1]

    return {"source": "odhad z okolia", "low": round(low, -2), "high": round(high, -2), "comps_count": len(comps)}
