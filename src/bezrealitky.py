import json
import re
import time

import requests

BASE_URL = "https://www.bezrealitky.cz"
SEARCH_PATH = "/vyhledat"
DETAIL_PATH = "/nemovitosti-byty-domy"
PAGE_SIZE = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
}

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_DISP_AND_MORE_RE = re.compile(r"_AND_MORE$")
_DISP_PAIR_RE = re.compile(r"(\d)_(\d)")


def _extract_next_data(html: str):
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    return json.loads(m.group(1))


def _format_disposition(raw: str) -> str:
    if not raw or not raw.startswith("DISP_"):
        return raw or "neuvedené"
    body = raw[len("DISP_"):]
    body = body.replace("_KK", "+kk")
    body = _DISP_AND_MORE_RE.sub("+", body)
    body = _DISP_PAIR_RE.sub(r"\1+\2", body)
    return body


def _find_list_query(root_query: dict):
    for key, value in root_query.items():
        if key.startswith("listAdverts(") and "discountedOnly" not in key:
            return value
    return None


def fetch_listings(max_price: int, min_price: int = 0, max_pages: int = 10, delay: float = 1.0):
    """Scrapes bezrealitky.cz search results (sale, flats), filtered to
    min_price <= price <= max_price. Only keeps CZK-priced listings, since
    the site also syndicates foreign (mostly German) partner listings that
    pass the numeric price filter but are irrelevant here."""
    listings = []
    page = 1
    while page <= max_pages:
        params = {"offerType": "PRODEJ", "estateType": "BYT", "priceTo": max_price, "page": page}
        if min_price:
            params["priceFrom"] = min_price
        resp = requests.get(BASE_URL + SEARCH_PATH, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = _extract_next_data(resp.text)
        if not data:
            break

        cache = data["props"]["pageProps"]["apolloCache"]
        root_query = cache.get("ROOT_QUERY", {})
        list_result = _find_list_query(root_query)
        if not list_result:
            break

        refs = list_result.get("list", [])
        if not refs:
            break

        for ref in refs:
            advert_id = ref["__ref"].split(":", 1)[1]
            advert = cache.get(ref["__ref"])
            if not advert:
                continue
            if advert.get("currency") != "CZK":
                continue  # zahraničný/partnerský inzerát v inej mene
            price = advert.get("price")
            floor = max(min_price, 50_000)
            if not price or price < floor or price > max_price:
                continue

            uri = advert.get("uri", advert_id)
            address = advert.get('address({"locale":"CS"})') or "neuvedené"
            dispozice = _format_disposition(advert.get("disposition", ""))

            listings.append(
                {
                    "source": "bezrealitky",
                    "id": advert_id,
                    "title": advert.get('imageAltText({"locale":"CS"})') or f"Byt {dispozice}",
                    "price": price,
                    "address": address,
                    "dispozice": dispozice,
                    "surface_m2": advert.get("surface"),
                    "url": f"{BASE_URL}{DETAIL_PATH}/{uri}",
                    "description": "",
                }
            )

        total = list_result.get("totalCount", 0)
        if page * PAGE_SIZE >= total:
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
    cache = data["props"]["pageProps"]["apolloCache"]
    id_match = re.search(r"/(\d+)-", url)
    if id_match:
        advert = cache.get(f"Advert:{id_match.group(1)}")
        if advert:
            return advert.get("description") or ""
    # fallback: pick the first Advert entry that actually has a description
    for key, value in cache.items():
        if key.startswith("Advert:") and value.get("description"):
            return value["description"]
    return ""
