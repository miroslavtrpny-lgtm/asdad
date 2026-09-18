import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "seen.json"
MAX_KEEP_PER_SOURCE = 6000


def load_state(path=DEFAULT_PATH):
    """Returns (state_dict, is_first_run). is_first_run is True when there is
    no prior history yet, so main.py can prime the seen-set instead of
    blasting Telegram with every currently-matching listing at once."""
    if not path.exists():
        return {"bazos": [], "sreality": []}, True
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("bazos", [])
    state.setdefault("sreality", [])
    is_first_run = not state["bazos"] and not state["sreality"]
    return state, is_first_run


def save_state(state, path=DEFAULT_PATH):
    trimmed = {k: v[-MAX_KEEP_PER_SOURCE:] for k, v in state.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)
