"""Best-effort guess of whether a flat currently has a tenant.

Neither Bazoš nor Sreality expose this as a structured field, so this is a
keyword search over the listing's free-text description. It is not reliable
- treat the result as a hint, not a fact.
"""
import re

_TENANT_YES = [
    r"s\s+n[aá]jemn[ií]k",
    r"pronaj[ae]t[aáoyí]*\b",
    r"obsazen[ýáé]?\s+n[aá]jemn",
    r"aktu[aá]ln[eě]\s+(?:pronaj|obsazen)",
    r"n[aá]jemn[ií]\s+smlouv",
    r"v[yý]nos\s+z\s+pron[aá]jmu",
    r"stávaj[íi]c[íi]m\s+n[aá]jemn",
]
_TENANT_NO = [
    r"voln[yý]\s+ihned",
    r"voln[aá]?\s+k\s+nast[eě]hov",
    r"bez\s+n[aá]jemn[ií]ka",
    r"neobsazen",
    r"k\s+okam[žz]it[eé]mu\s+nast[eě]hov[aá]n[ií]",
    r"voln[eé]\s+k\s+pod?ed[aá]n[ií]",
]

_YES_RE = re.compile("|".join(_TENANT_YES), re.IGNORECASE)
_NO_RE = re.compile("|".join(_TENANT_NO), re.IGNORECASE)


def detect_tenant(text: str) -> str:
    if not text:
        return "neuvedené"
    has_yes = bool(_YES_RE.search(text))
    has_no = bool(_NO_RE.search(text))
    if has_yes and not has_no:
        return "áno (podľa textu inzerátu)"
    if has_no and not has_yes:
        return "nie, voľný (podľa textu inzerátu)"
    return "neuvedené"
