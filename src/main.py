import html
import os
import sys
import time

from . import bazos, sreality, state as state_mod, tenant

SOURCE_LABELS = {"bazos": "Bazoš.cz", "sreality": "Sreality.cz"}


def _format_message(listing: dict, max_price: int) -> str:
    price_fmt = f"{listing['price']:,}".replace(",", " ")
    max_price_fmt = f"{max_price:,}".replace(",", " ")
    return (
        f"🏠 <b>Nový byt do {max_price_fmt} Kč</b> ({SOURCE_LABELS[listing['source']]})\n"
        f"{html.escape(listing['title'])}\n\n"
        f"📍 Adresa: {html.escape(listing['address'])}\n"
        f"📐 Dispozícia: {html.escape(listing['dispozice'])}\n"
        f"💰 Cena: {price_fmt} Kč\n"
        f"🧑‍🤝‍🧑 Nájomník: {html.escape(listing['tenant'])}\n\n"
        f"🔗 {listing['url']}"
    )


def _resolve_description(listing: dict) -> str:
    try:
        if listing["source"] == "bazos":
            full = bazos.fetch_full_description(listing["url"])
        else:
            full = sreality.fetch_full_description(listing["url"])
        return full or listing.get("description", "")
    except Exception as exc:  # noqa: BLE001 - best effort, never let this break the run
        print(f"  varovanie: nepodarilo sa načítať detail {listing['url']}: {exc}", file=sys.stderr)
        return listing.get("description", "")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    max_price = int(os.environ.get("MAX_PRICE_CZK", "1300000"))

    from . import telegram  # imported here so a first (priming) run works without credentials

    seen, first_run = state_mod.load_state()
    seen_ids = {source: set(ids) for source, ids in seen.items()}

    print("Sťahujem inzeráty z Bazoš.cz...")
    bazos_listings = bazos.fetch_listings(max_price)
    print(f"  nájdených {len(bazos_listings)} inzerátov do {max_price} Kč")

    print("Sťahujem inzeráty zo Sreality.cz...")
    sreality_listings = sreality.fetch_listings(max_price)
    print(f"  nájdených {len(sreality_listings)} inzerátov do {max_price} Kč")

    all_listings = bazos_listings + sreality_listings

    if first_run:
        for listing in all_listings:
            seen_ids[listing["source"]].add(listing["id"])
        state_mod.save_state({k: sorted(v) for k, v in seen_ids.items()})
        print(
            f"Prvý beh: {len(all_listings)} existujúcich inzerátov označených ako videných, "
            "bez odoslania na Telegram. Od ďalšieho behu prídu už len nové inzeráty."
        )
        return

    if not token or not chat_id:
        raise SystemExit(
            "Chýba TELEGRAM_BOT_TOKEN alebo TELEGRAM_CHAT_ID - nastav ich ako "
            "premenné prostredia (lokálne cez .env, na GitHub cez repo Secrets)."
        )

    new_count = 0
    for listing in all_listings:
        source, listing_id = listing["source"], listing["id"]
        if listing_id in seen_ids[source]:
            continue
        seen_ids[source].add(listing_id)

        full_description = _resolve_description(listing)
        listing["tenant"] = tenant.detect_tenant(full_description)

        message = _format_message(listing, max_price)
        try:
            telegram.send_message(token, chat_id, message)
            new_count += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  chyba pri odosielaní na Telegram ({listing['url']}): {exc}", file=sys.stderr)
        time.sleep(1)

    state_mod.save_state({k: sorted(v) for k, v in seen_ids.items()})
    print(f"Hotovo. Nových inzerátov odoslaných na Telegram: {new_count}")


if __name__ == "__main__":
    main()
