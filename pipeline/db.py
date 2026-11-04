"""Acesso ao Postgres (Supabase): migrações e upserts idempotentes."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from .config import Source
from .f1data import ConstructorStanding, DriverStanding, Race
from .news import Article

log = logging.getLogger(__name__)


def connect(database_url: str) -> psycopg.Connection:
    # prepare_threshold=None: obrigatório com o pooler do Supabase em modo transaction (porta 6543)
    # autocommit=True: cada bloco `conn.transaction()` é uma transação real e explícita
    return psycopg.connect(
        database_url,
        prepare_threshold=None,
        connect_timeout=20,
        autocommit=True,
        application_name="painel-f1-pipeline",
    )


def migrate(conn: psycopg.Connection, migrations_dir: Path) -> list[str]:
    """Aplica, em ordem, os arquivos .sql ainda não registrados."""
    with conn.transaction():
        conn.execute("""
            create table if not exists public.f1_schema_migrations (
                version    text primary key,
                checksum   text not null,
                applied_at timestamptz not null default now()
            )""")
        conn.execute("alter table public.f1_schema_migrations enable row level security")
        applied = {row[0] for row in conn.execute("select version from public.f1_schema_migrations")}

    done = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.stem in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        with conn.transaction():
            conn.execute(sql)
            conn.execute(
                "insert into public.f1_schema_migrations (version, checksum) values (%s, %s)",
                (path.stem, hashlib.sha256(sql.encode()).hexdigest()),
            )
        log.info("Migração aplicada: %s", path.name)
        done.append(path.stem)
    return done


def sync_sources(conn: psycopg.Connection, sources: Iterable[Source]) -> dict[str, int]:
    with conn.transaction(), conn.cursor() as cur:
        for s in sources:
            cur.execute(
                """insert into public.f1_sources (slug, name, homepage, feed_url, language, is_active)
                   values (%s, %s, %s, %s, %s, true)
                   on conflict (slug) do update set
                     name = excluded.name, homepage = excluded.homepage,
                     feed_url = excluded.feed_url, language = excluded.language, is_active = true
                   where (f1_sources.name, f1_sources.homepage, f1_sources.feed_url,
                          f1_sources.language, f1_sources.is_active)
                     is distinct from
                         (excluded.name, excluded.homepage, excluded.feed_url,
                          excluded.language, excluded.is_active)""",
                (s.slug, s.name, s.homepage, s.feed_url, s.language),
            )
        cur.execute("select slug, id from public.f1_sources")
        return dict(cur.fetchall())


def known_images(conn: psycopg.Connection, urls: list[str]) -> dict[str, str]:
    if not urls:
        return {}
    rows = conn.execute(
        "select url, image_url from public.f1_articles where url = any(%s) and image_url is not null",
        (urls,),
    ).fetchall()
    return dict(rows)


def upsert_articles(conn: psycopg.Connection, articles: list[Article], source_ids: dict[str, int]) -> int:
    rows = [
        (
            source_ids[a.source_slug],
            a.url,
            a.title,
            a.summary,
            a.image_url,
            a.author,
            a.tags,
            a.language,
            a.published_at,
        )
        for a in articles
    ]
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """insert into public.f1_articles
                 (source_id, url, title, summary, image_url, author, tags, language, published_at)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               on conflict (url) do update set
                 title     = excluded.title,
                 summary   = coalesce(excluded.summary, f1_articles.summary),
                 image_url = coalesce(excluded.image_url, f1_articles.image_url),
                 author    = coalesce(excluded.author, f1_articles.author),
                 tags      = excluded.tags
               where (f1_articles.title, f1_articles.summary, f1_articles.image_url, f1_articles.tags)
                 is distinct from
                     (excluded.title, coalesce(excluded.summary, f1_articles.summary),
                      coalesce(excluded.image_url, f1_articles.image_url), excluded.tags)""",
            rows,
        )
    return len(rows)


def _upsert(conn: psycopg.Connection, table: str, key: tuple[str, ...], items: list) -> int:
    if not items:
        return 0
    cols = list(asdict(items[0]).keys())
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in key)
    sql = (
        f"insert into public.{table} ({', '.join(cols)}) "
        f"values ({', '.join(['%s'] * len(cols))}) "
        f"on conflict ({', '.join(key)}) do update set {updates}"
    )
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(sql, [tuple(asdict(i).values()) for i in items])
    return len(items)


def upsert_races(conn, races: list[Race]) -> int:
    return _upsert(conn, "f1_races", ("season", "round"), races)


def replace_driver_standings(conn, rows: list[DriverStanding]) -> int:
    if not rows:
        return 0
    with conn.transaction():
        conn.execute(
            "delete from public.f1_driver_standings where season = %s and driver_id <> all(%s)",
            (rows[0].season, [r.driver_id for r in rows]),
        )
        return _upsert(conn, "f1_driver_standings", ("season", "driver_id"), rows)


def replace_constructor_standings(conn, rows: list[ConstructorStanding]) -> int:
    if not rows:
        return 0
    with conn.transaction():
        conn.execute(
            "delete from public.f1_constructor_standings where season = %s and constructor_id <> all(%s)",
            (rows[0].season, [r.constructor_id for r in rows]),
        )
        return _upsert(conn, "f1_constructor_standings", ("season", "constructor_id"), rows)


def purge_old_articles(conn, retention_days: int) -> int:
    with conn.transaction():
        cur = conn.execute(
            "delete from public.f1_articles where published_at < now() - make_interval(days => %s)",
            (retention_days,),
        )
    return cur.rowcount


def start_run(conn, trigger: str | None) -> int:
    with conn.transaction():
        return conn.execute(
            "insert into public.f1_pipeline_runs (trigger) values (%s) returning id", (trigger,)
        ).fetchone()[0]


def finish_run(conn, run_id: int, status: str, found: int, upserted: int, details: dict) -> None:
    with conn.transaction():
        conn.execute(
            """update public.f1_pipeline_runs
               set finished_at = now(), status = %s, articles_found = %s,
                   articles_upserted = %s, details = %s
               where id = %s""",
            (status, found, upserted, Jsonb(json.loads(json.dumps(details, default=str))), run_id),
        )
