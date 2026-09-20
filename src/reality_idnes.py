import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://reality.idnes.cz"
SEARCH_PATH = "/s/prodej/byty/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
}

_DISPOZICE_RE = re.compile(r"([1-6]\s*\+\s*(?:kk|k|[1-6]))", re.IGNORECASE)
_ID_RE = re.compile(r"/detail/[^/]+/[^/]+/[^/]+/([0-9a-f]+)/?$")

# reality.idnes.cz miesi medzi "byty" aj zahraničné ponuky (Egypt, Bulharsko,
# Itálie...), ktoré numericky prejdú cenovým filtrom - adresa u nich vždy
# končí názvom krajiny, u českých inzerátov nikdy.
_FOREIGN_COUNTRIES = [
    "egypt", "bulharsko", "itálie", "chorvatsko", "španělsko", "řecko",
    "turecko", "albánie", "černá hora", "slovinsko", "francie",
    "portugalsko", "rakousko", "německo", "slovensko", "polsko",
    "maďarsko", "omán", "thajsko", "indonésie", "bali", "dubaj",
    "emiráty", "kypr", "makedonie", "srbsko", "bosna",
]


def _parse_price(text: str):
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _is_foreign(address: str) -> bool:
    lowered = (address or "").lower()
    return any(country in lowered for country in _FOREIGN_COUNTRIES)


def fetch_listings(max_price: int, max_pages: int = 1, delay: float = 1.0):
    """Scrapes reality.idnes.cz search results (sale, flats) filtered to
    price <= max_price. iDNES doesn't reliably paginate this search (the
    `str` page parameter has no effect once results fit on one page), so
    for the price ranges this bot targets a single page already covers the
    full result set."""
    listings = []
    for page in range(1, max_pages + 1):
        params = {"f[priceMax]": max_price}
        if page > 1:
            params["str"] = page
        resp = requests.get(BASE_URL + SEARCH_PATH, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div.c-products__item")
        if not cards:
            break

        for card in cards:
            if "c-products__item-advertisment" in card.get("class", []):
                continue
            link_el = card.select_one("a.c-products__link")
            if not link_el or not link_el.get("href"):
                continue
            href = link_el["href"]
            id_match = _ID_RE.search(href)
            if not id_match:
                continue
            listing_id = id_match.group(1)

            title_el = card.select_one("h2.c-products__title")
            title = title_el.get_text(" ", strip=True) if title_el else ""

            address_el = card.select_one("p.c-products__info")
            address = address_el.get_text(strip=True) if address_el else "neuvedené"
            if _is_foreign(address):
                continue

            price_el = card.select_one("p.c-products__price strong")
            price = _parse_price(price_el.get_text() if price_el else "")
            if price is None or price < 50_000 or price > max_price:
                continue

            disp_match = _DISPOZICE_RE.search(title)
            dispozice = disp_match.group(1).replace(" ", "") if disp_match else "neuvedené"

            listings.append(
                {
                    "source": "reality_idnes",
                    "id": listing_id,
                    "title": title,
                    "price": price,
                    "address": address,
                    "dispozice": dispozice,
                    "url": href,
                    "description": "",
                }
            )

        time.sleep(delay)

    return listings


def fetch_full_description(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    el = soup.select_one("div.b-desc")
    return el.get_text("\n", strip=True) if el else ""
