"""Configuração carregada de variáveis de ambiente e do catálogo de fontes."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

SOURCES_FILE = Path(__file__).with_name("sources.toml")
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"


@dataclass(frozen=True, slots=True)
class Source:
    slug: str
    name: str
    homepage: str
    feed_url: str
    language: str
    f1_only: bool = True


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    max_articles_per_source: int = 40
    max_article_age_days: int = 7
    retention_days: int = 90
    http_timeout: float = 20.0
    enrich_images_limit: int = 30
    f1_api_base: str = "https://api.jolpi.ca/ergast/f1"
    user_agent: str = (
        "Mozilla/5.0 (compatible; PainelF1Bot/1.0; +https://github.com/afonsolelis/painel-pessoal)"
    )
    sources: tuple[Source, ...] = field(default_factory=tuple)

    @classmethod
    def from_env(cls) -> Settings:
        database_url = os.environ.get("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("Variável de ambiente DATABASE_URL não definida.")
        return cls(
            database_url=database_url,
            max_articles_per_source=int(os.environ.get("MAX_ARTICLES_PER_SOURCE", 40)),
            max_article_age_days=int(os.environ.get("MAX_ARTICLE_AGE_DAYS", 7)),
            retention_days=int(os.environ.get("RETENTION_DAYS", 90)),
            sources=load_sources(),
        )


def load_sources(path: Path = SOURCES_FILE) -> tuple[Source, ...]:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    sources = tuple(Source(**item) for item in data.get("source", []))
    slugs = [s.slug for s in sources]
    if len(slugs) != len(set(slugs)):
        raise ValueError("Slugs duplicados em sources.toml")
    for s in sources:
        if s.language not in {"pt", "en"}:
            raise ValueError(f"Idioma inválido para {s.slug}: {s.language}")
    return sources
