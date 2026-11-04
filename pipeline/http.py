"""Sessão HTTP com retentativas e backoff exponencial."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_session(user_agent: str) -> requests.Session:
    retry = Retry(
        total=4,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return session
