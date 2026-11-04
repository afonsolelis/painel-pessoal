"""Funções puras de normalização de texto e URLs."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

_TRACKING_PREFIXES = ("utm_", "at_", "mc_", "fbclid", "gclid", "ocid", "cmpid", "xtor")
_WS = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?…])")

F1_KEYWORDS = re.compile(
    r"\b(f1|f[óo]rmula\s*1|formula\s*one|formula\s*1|grand\s*prix|grande\s*pr[êe]mio|gp\s+d[aeo])\b",
    re.IGNORECASE,
)


def canonical_url(url: str) -> str:
    """Remove parâmetros de rastreamento e fragmentos para deduplicar URLs."""
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    scheme = "https" if parts.scheme in {"http", "https"} else parts.scheme
    return urlunsplit((scheme, parts.netloc.lower(), parts.path, urlencode(query), ""))


def is_http_url(url: str | None) -> bool:
    if not url:
        return False
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def clean_html(raw: str | None, max_len: int = 400) -> str | None:
    """Converte HTML em texto limpo e trunca em limite de palavra."""
    if not raw:
        return None
    text = BeautifulSoup(raw, "html.parser").get_text(" ")
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", _WS.sub(" ", html.unescape(text))).strip()
    if not text:
        return None
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return text


def first_image_in_html(raw: str | None) -> str | None:
    if not raw:
        return None
    img = BeautifulSoup(raw, "html.parser").find("img", src=True)
    src = img["src"] if img else None
    return src if is_http_url(src) else None


def looks_like_f1(*texts: str | None) -> bool:
    return any(t and F1_KEYWORDS.search(t) for t in texts)
