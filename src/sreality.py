import json
import re
import time

import requests

BASE_URL = "https://www.sreality.cz"
SEARCH_PATH = "/hledani/prodej/byty"
PAGE_SIZE = 22

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
}

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_DETAIL_HREF_RE = re.compile(r'href="(/detail/prodej/byt/[^"?]*?/(\d+))"')


def _extract_next_data(html: str):
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    return json.loads(m.group(1))


def _format_address(locality: dict) -> str:
    parts = []
    street = locality.get("street")
    house_number = locality.get("houseNumber")
    if street:
        parts.append(f"{street}{' ' + house_number if house_number else ''}")
    city_part = locality.get("cityPart")
    city = locality.get("city")
    if city_part and city_part != city:
        parts.append(city_part)
    if city:
        parts.append(city)
    return ", ".join(parts) if parts else "neuvedené"


def fetch_listings(max_price: int, max_pages: int = 20, delay: float = 1.0):
    """Scrapes sreality.cz search results (sale, flats) filtered to
    price <= max_price, across the whole Czech Republic (default locality
    scope of sreality.cz). Returns a list of dicts."""
    listings = []
    page = 1
    while page <= max_pages:
        params = {"cena-do": max_price, "strana": page}
        resp = requests.get(BASE_URL + SEARCH_PATH, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
        data = _extract_next_data(html)
        if not data:
            break

        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        search_q = next((q for q in queries if q["queryKey"][0] == "estatesSearch"), None)
        if not search_q:
            break
        result_data = search_q["state"]["data"]
        results = result_data.get("results", [])
        if not results:
            break

        id_to_href = {m.group(2): m.group(1) for m in _DETAIL_HREF_RE.finditer(html)}

        for r in results:
            price = r.get("priceCzk")
            if not price or price <= 0 or price > max_price:
                continue
            listing_id = str(r["id"])
            href = id_to_href.get(listing_id)
            url = BASE_URL + href if href else f"{BASE_URL}/detail/prodej/byt/id/{listing_id}"

            dispozice = (r.get("categorySubCb") or {}).get("name", "neuvedené")
            address = _format_address(r.get("locality", {}))
            price_per_m2 = r.get("priceCzkPerSqM")
            surface_m2 = round(price / price_per_m2) if price_per_m2 else None

            listings.append(
                {
                    "source": "sreality",
                    "id": listing_id,
                    "title": r.get("name", ""),
                    "price": price,
                    "address": address,
                    "city": (r.get("locality") or {}).get("city"),
                    "dispozice": dispozice,
                    "surface_m2": surface_m2,
                    "url": url,
                    "description": "",
                }
            )

        pagination = result_data.get("pagination", {})
        total = pagination.get("total", 0)
        if pagination.get("offset", 0) + len(results) >= total:
            break
        page += 1
        time.sleep(delay)

    return listings


def fetch_full_description(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    data = _extract_next_data(resp.text)
    if not data:
        return ""
    queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
    q = next((q for q in queries if q["queryKey"][0] == "estate"), None)
    if not q:
        return ""
    return q["state"]["data"].get("description") or ""
