import html
import os
import sys
import time

from . import bazos, bezrealitky, sreality, state as state_mod, tenant

SOURCES = {
    "bazos": bazos,
    "sreality": sreality,
    "bezrealitky": bezrealitky,
}
SOURCE_LABELS = {
    "bazos": "Bazoš.cz",
    "sreality": "Sreality.cz",
    "bezrealitky": "Bezrealitky.cz",
}
NABIDKA_CHUNK_LIMIT = 3500


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
        module = SOURCES[listing["source"]]
        full = module.fetch_full_description(listing["url"])
        return full or listing.get("description", "")
    except Exception as exc:  # noqa: BLE001 - best effort, never let this break the run
        print(f"  varovanie: nepodarilo sa načítať detail {listing['url']}: {exc}", file=sys.stderr)
        return listing.get("description", "")


def _reply_nabidka(telegram, token: str, chat_id: str, listings: list, max_price: int) -> None:
    max_price_fmt = f"{max_price:,}".replace(",", " ")
    if not listings:
        telegram.send_message(token, chat_id, f"Aktuálne nie je v ponuke žiadny byt do {max_price_fmt} Kč.")
        return

    ordered = sorted(listings, key=lambda l: l["price"])
    header = f"📋 <b>Aktuálne byty do {max_price_fmt} Kč</b> ({len(ordered)} inzerátov):\n\n"

    lines = []
    for i, listing in enumerate(ordered, 1):
        price_fmt = f"{listing['price']:,}".replace(",", " ")
        lines.append(
            f"{i}. {price_fmt} Kč | {html.escape(listing['dispozice'])} | "
            f"{html.escape(listing['address'])} | {SOURCE_LABELS[listing['source']]}\n{listing['url']}"
        )

    chunk = header
    for line in lines:
        candidate = f"{chunk}{line}\n\n"
        if len(candidate) > NABIDKA_CHUNK_LIMIT and chunk != header:
            telegram.send_message(token, chat_id, chunk.rstrip())
            time.sleep(1)
            chunk = f"{line}\n\n"
        else:
            chunk = candidate
    if chunk.strip():
        telegram.send_message(token, chat_id, chunk.rstrip())


def _handle_commands(telegram, token: str, chat_id: str, last_update_id: int, all_listings: list, max_price: int) -> int:
    try:
        updates = telegram.get_updates(token, offset=last_update_id + 1)
    except Exception as exc:  # noqa: BLE001 - never let a Telegram hiccup break the scan
        print(f"  chyba pri čítaní Telegram príkazov: {exc}", file=sys.stderr)
        return last_update_id

    new_last_update_id = last_update_id
    for update in updates:
        new_last_update_id = max(new_last_update_id, update.get("update_id", new_last_update_id))
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        if not text:
            continue
        msg_chat_id = str(message.get("chat", {}).get("id", ""))
        if msg_chat_id != str(chat_id):
            continue  # ignoruj príkazy z iných chatov, nie je to náš nakonfigurovaný chat

        command = text.split()[0].split("@")[0].lower()
        if command == "/nabidka":
            print(f"  prijatý príkaz /nabidka (chat {msg_chat_id})")
            try:
                _reply_nabidka(telegram, token, chat_id, all_listings, max_price)
            except Exception as exc:  # noqa: BLE001
                print(f"  chyba pri odpovedi na /nabidka: {exc}", file=sys.stderr)

    return new_last_update_id


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    max_price = int(os.environ.get("MAX_PRICE_CZK") or "1000000")

    from . import telegram  # imported here so a first (priming) run works without credentials

    source_names = tuple(SOURCES.keys())
    seen, first_run = state_mod.load_state(sources=source_names)
    seen_ids = {name: set(seen[name]) for name in source_names}
    last_update_id = seen.get("last_update_id", 0)

    all_listings = []
    for name, module in SOURCES.items():
        print(f"Sťahujem inzeráty z {SOURCE_LABELS[name]}...")
        listings = module.fetch_listings(max_price)
        print(f"  nájdených {len(listings)} inzerátov do {max_price} Kč")
        all_listings.extend(listings)

    if token and chat_id:
        last_update_id = _handle_commands(telegram, token, chat_id, last_update_id, all_listings, max_price)

    if first_run:
        for listing in all_listings:
            seen_ids[listing["source"]].add(listing["id"])
        state_to_save = {name: sorted(ids) for name, ids in seen_ids.items()}
        state_to_save["last_update_id"] = last_update_id
        state_mod.save_state(state_to_save, sources=source_names)
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

    state_to_save = {name: sorted(ids) for name, ids in seen_ids.items()}
    state_to_save["last_update_id"] = last_update_id
    state_mod.save_state(state_to_save, sources=source_names)
    print(f"Hotovo. Nových inzerátov odoslaných na Telegram: {new_count}")


if __name__ == "__main__":
    main()
