import requests

_BASE_URL = "https://api.telegram.org/bot{token}"


def send_message(token: str, chat_id: str, text: str) -> dict:
    resp = requests.post(
        f"{_BASE_URL.format(token=token)}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def get_updates(token: str, offset: int | None = None, timeout: int = 0) -> list:
    """Fetches pending updates (e.g. commands typed in the chat) since `offset`.
    timeout=0 means a plain non-blocking poll, which is what we want since this
    runs inside a short-lived cron job rather than a long-running process."""
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(
        f"{_BASE_URL.format(token=token)}/getUpdates",
        params=params,
        timeout=timeout + 20,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])
