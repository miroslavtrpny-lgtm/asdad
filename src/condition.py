"""Best-effort guess of a flat's renovation state from its description text.

Like tenant.py, this is a keyword search - not a structured field most
sources expose - so treat the result as a hint, not a fact.
"""
import re

_NOVOSTAVBA = [r"novostavb", r"nov[eě]\s+postaven"]
_PO_REKONSTRUKCI = [
    r"po\s+(?:kompletn[íi]\s+)?rekonstrukci",
    r"kompletn[eě]\s+zrekonstruovan",
    r"celkov[eě]\s+zrekonstruovan",
    r"\bzrekonstruovan[ýáé]",
    r"po\s+rekonstrukci",
]
_PRED_REKONSTRUKCI = [
    r"p[řr]ed\s+rekonstrukc",
    r"k\s+rekonstrukci",
    r"vy[žz]aduje\s+rekonstrukci",
    r"pot[řr]eba\s+rekonstrukce",
    r"nutn[aá]\s+rekonstrukce",
    r"havarijn[íi]m?\s+stav",
    r"[šs]patn[ýéí]m?\s+stavu?",
    r"k\s+opravě",
    r"p[ůu]vodn[íi]m?\s+stavu",
    r"v\s+rekonstrukci",
]

_NOVOSTAVBA_RE = re.compile("|".join(_NOVOSTAVBA), re.IGNORECASE)
_PO_REKONSTRUKCI_RE = re.compile("|".join(_PO_REKONSTRUKCI), re.IGNORECASE)
_PRED_REKONSTRUKCI_RE = re.compile("|".join(_PRED_REKONSTRUKCI), re.IGNORECASE)


def detect_condition(text: str) -> str:
    if not text:
        return "neuvedený"
    if _NOVOSTAVBA_RE.search(text):
        return "novostavba"
    if _PRED_REKONSTRUKCI_RE.search(text):
        return "potrebná rekonštrukcia (podľa textu)"
    if _PO_REKONSTRUKCI_RE.search(text):
        return "po rekonštrukcii (podľa textu)"
    return "neuvedený"
