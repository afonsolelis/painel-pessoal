from datetime import UTC, datetime, timedelta
from pathlib import Path

from pipeline.config import Source, load_sources
from pipeline.news import parse_feed

FIXTURE = (Path(__file__).parent / "fixtures" / "feed_mixed.xml").read_bytes()
NOW = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)


def _source(f1_only: bool) -> Source:
    return Source("mix", "Mix", "https://example.com", "https://example.com/rss", "pt", f1_only)


def test_parse_filters_dedupes_and_normalizes():
    items = parse_feed(FIXTURE, _source(f1_only=False), now=NOW, max_items=50, max_age=timedelta(days=7))
    assert [a.url for a in items] == ["https://example.com/f1/verstappen-tl1?id=7"]
    art = items[0]
    assert art.summary == "Holandês foi o mais rápido."
    assert art.image_url == "https://example.com/img/1.jpg"
    assert art.language == "pt"
    assert art.tags == ["Fórmula 1"]
    assert art.published_at == datetime(2026, 11, 4, 14, 0, tzinfo=UTC)


def test_f1_only_source_keeps_non_keyword_items():
    items = parse_feed(FIXTURE, _source(f1_only=True), now=NOW, max_items=50, max_age=timedelta(days=60))
    assert len(items) == 3
    assert items[-1].image_url == "https://example.com/img/old.jpg"


def test_max_items_is_respected():
    items = parse_feed(FIXTURE, _source(f1_only=True), now=NOW, max_items=1, max_age=timedelta(days=60))
    assert len(items) == 1


def test_sources_catalog_has_both_languages():
    sources = load_sources()
    assert {s.language for s in sources} == {"pt", "en"}
