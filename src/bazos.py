import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://reality.bazos.cz"
SEARCH_PATH = "/prodam/byt/"
PAGE_SIZE = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
}

_DISPOZICE_RE = re.compile(r"([1-6]\s*\+\s*(?:kk|k|[1-6]))", re.IGNORECASE)
_ID_RE = re.compile(r"/inzerat/(\d+)/")


def _parse_price(text: str):
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def fetch_listings(max_price: int, max_pages: int = 20, delay: float = 1.0):
    """Scrapes reality.bazos.cz/prodam/byt/ filtered to price <= max_price,
    across the whole Czech Republic. Returns a list of dicts."""
    listings = []
    offset = 0
    while offset < max_pages * PAGE_SIZE:
        params = {
            "hledat": "",
            "rubriky": "reality",
            "hlokalita": "",
            "humkreis": 0,
            "cenaod": "",
            "cenado": max_price,
            "Submit": "Hledat",
            "order": "",
            "crp": offset,
            "kitx": "ano",
        }
        resp = requests.get(BASE_URL + SEARCH_PATH, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div.inzeraty.inzeratyflex")
        if not cards:
            break

        for card in cards:
            link_el = card.select_one(".inzeratynadpis h2.nadpis a")
            if not link_el or not link_el.get("href"):
                continue
            href = link_el["href"]
            id_match = _ID_RE.search(href)
            if not id_match:
                continue
            listing_id = id_match.group(1)

            title = link_el.get_text(strip=True)
            desc_el = card.select_one(".popis")
            description = desc_el.get_text(strip=True) if desc_el else ""

            if re.search(r"v[yý]m[ěe]n|vym[eě]n[íi]m", title, re.IGNORECASE):
                continue  # bytová výměna, nie predaj - nemá skutočnú cenu

            price_el = card.select_one(".inzeratycena")
            price = _parse_price(price_el.get_text() if price_el else "")
            # skutočný byt sa reálne neinzeruje pod ~50 000 Kč - nižšie ceny sú
            # symbolické (výmena, dohodou a pod.), preto ich preskočíme
            if price is None or price < 50_000 or price > max_price:
                continue

            loc_el = card.select_one(".inzeratylok")
            loc_text = loc_el.get_text(separator=" ", strip=True) if loc_el else ""
            city = loc_text.split(" ")[0] if loc_text else ""
            if "zahran" in city.lower():
                continue

            disp_match = _DISPOZICE_RE.search(title) or _DISPOZICE_RE.search(description)
            dispozice = disp_match.group(1).replace(" ", "") if disp_match else "neuvedené"

            listings.append(
                {
                    "source": "bazos",
                    "id": listing_id,
                    "title": title,
                    "price": price,
                    "address": loc_text or "neuvedené",
                    "dispozice": dispozice,
                    "url": BASE_URL + href,
                    "description": description,
                }
            )

        if len(cards) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(delay)

    return listings


def fetch_full_description(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    el = soup.select_one(".popisdetail")
    return el.get_text(strip=True) if el else ""
