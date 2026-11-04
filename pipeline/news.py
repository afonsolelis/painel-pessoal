"""Coleta e normalização de manchetes a partir de feeds RSS/Atom."""

from __future__ import annotations

import calendar
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import feedparser
import requests
from bs4 import BeautifulSoup

from .config import Source
from .text import canonical_url, clean_html, first_image_in_html, is_http_url, looks_like_f1

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Article:
    source_slug: str
    url: str
    title: str
    language: str
    published_at: datetime
    summary: str | None = None
    image_url: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)


def _published(entry: dict, fallback: datetime) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            return datetime.fromtimestamp(calendar.timegm(struct), tz=UTC)
    return fallback


def _image(entry: dict) -> str | None:
    for key in ("media_content", "media_thumbnail"):
        for media in entry.get(key) or []:
            if is_http_url(media.get("url")):
                return media["url"]
    for link in entry.get("links") or []:
        is_image = link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image")
        if is_image and is_http_url(link.get("href")):
            return link["href"]
    content = (entry.get("content") or [{}])[0].get("value")
    return first_image_in_html(content) or first_image_in_html(entry.get("summary"))


def parse_feed(
    content: bytes, source: Source, *, now: datetime, max_items: int, max_age: timedelta
) -> list[Article]:
    """Converte o XML do feed em artigos normalizados (função pura, testável)."""
    feed = feedparser.parse(content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"Feed inválido: {feed.bozo_exception}")

    articles: list[Article] = []
    seen: set[str] = set()
    for entry in feed.entries:
        link, title = entry.get("link"), clean_html(entry.get("title"), max_len=300)
        if not title or not is_http_url(link):
            continue
        url = canonical_url(link)
        if url in seen:
            continue

        tags = [t.get("term", "").strip() for t in entry.get("tags") or [] if t.get("term")]
        summary = clean_html(entry.get("summary"))
        if not source.f1_only and not looks_like_f1(title, summary, " ".join(tags)):
            continue

        published = min(_published(entry, now), now)
        if now - published > max_age:
            continue

        seen.add(url)
        articles.append(
            Article(
                source_slug=source.slug,
                url=url,
                title=title,
                language=source.language,
                published_at=published,
                summary=summary,
                image_url=_image(entry),
                author=(entry.get("author") or None),
                tags=tags[:10],
            )
        )
        if len(articles) >= max_items:
            break
    return articles


def fetch_source(
    session: requests.Session, source: Source, *, timeout: float, max_items: int, max_age: timedelta
) -> list[Article]:
    response = session.get(source.feed_url, timeout=timeout)
    response.raise_for_status()
    return parse_feed(response.content, source, now=datetime.now(UTC), max_items=max_items, max_age=max_age)


def _og_image(session: requests.Session, url: str, timeout: float) -> str | None:
    try:
        resp = session.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        head = resp.raw.read(300_000, decode_content=True)  # o <head> basta
        resp.close()
    except (requests.RequestException, OSError) as exc:
        log.debug("og:image falhou para %s: %s", url, exc)
        return None
    soup = BeautifulSoup(head, "html.parser")
    for attr, name in (("property", "og:image"), ("name", "twitter:image")):
        tag = soup.find("meta", attrs={attr: name})
        if tag and is_http_url(tag.get("content")):
            return tag["content"]
    return None


def enrich_images(session: requests.Session, articles: list[Article], *, limit: int, timeout: float) -> int:
    """Busca og:image para artigos sem imagem (limitado para ser educado com os sites)."""
    missing = [a for a in articles if not a.image_url][:limit]
    if not missing:
        return 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        images = list(pool.map(lambda a: _og_image(session, a.url, timeout), missing))
    found = 0
    for article, image in zip(missing, images, strict=True):
        if image:
            article.image_url, found = image, found + 1
    return found
