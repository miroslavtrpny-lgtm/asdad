import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "seen.json"
MAX_KEEP_PER_SOURCE = 6000
DEFAULT_SOURCES = ("bazos", "sreality", "bezrealitky")


def load_state(path=DEFAULT_PATH, sources=DEFAULT_SOURCES):
    """Returns (state_dict, is_first_run). is_first_run is True when there is
    no prior history yet for any known source, so main.py can prime the
    seen-set instead of blasting Telegram with every currently-matching
    listing at once."""
    if not path.exists():
        state = {s: [] for s in sources}
        state["last_update_id"] = 0
        return state, True
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    for s in sources:
        state.setdefault(s, [])
    state.setdefault("last_update_id", 0)
    is_first_run = all(not state[s] for s in sources)
    return state, is_first_run


def save_state(state, path=DEFAULT_PATH, sources=DEFAULT_SOURCES):
    trimmed = {s: state.get(s, [])[-MAX_KEEP_PER_SOURCE:] for s in sources}
    trimmed["last_update_id"] = state.get("last_update_id", 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)
