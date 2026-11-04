"""Ponto de entrada: `python -m pipeline`.

Etapas: migrações -> fontes -> notícias (RSS) -> dados esportivos -> retenção -> auditoria.
Uma fonte com falha não derruba o pipeline; o status final vira `partial`.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import timedelta

from . import db, f1data, news
from .config import MIGRATIONS_DIR, Settings
from .http import build_session

log = logging.getLogger("pipeline")


def run(settings: Settings, *, migrate_only: bool = False) -> int:
    session = build_session(settings.user_agent)
    with db.connect(settings.database_url) as conn:
        applied = db.migrate(conn, MIGRATIONS_DIR)
        log.info("Migrações novas: %s", applied or "nenhuma")
        if migrate_only:
            return 0

        run_id = db.start_run(conn, os.environ.get("GITHUB_EVENT_NAME", "manual"))
        details: dict = {"sources": {}, "errors": []}
        articles: list[news.Article] = []
        status = "success"

        try:
            source_ids = db.sync_sources(conn, settings.sources)

            for source in settings.sources:
                try:
                    items = news.fetch_source(
                        session,
                        source,
                        timeout=settings.http_timeout,
                        max_items=settings.max_articles_per_source,
                        max_age=timedelta(days=settings.max_article_age_days),
                    )
                    articles.extend(items)
                    details["sources"][source.slug] = len(items)
                    log.info("%-16s %3d manchetes", source.slug, len(items))
                except Exception as exc:  # noqa: BLE001 - isolamento por fonte
                    status = "partial"
                    details["sources"][source.slug] = 0
                    details["errors"].append(f"{source.slug}: {exc}")
                    log.warning("Falha na fonte %s: %s", source.slug, exc)

            # Reaproveita imagens já conhecidas e só busca og:image do que falta.
            cached = db.known_images(conn, [a.url for a in articles if not a.image_url])
            for a in articles:
                a.image_url = a.image_url or cached.get(a.url)
            details["og_images"] = news.enrich_images(
                session, articles, limit=settings.enrich_images_limit, timeout=settings.http_timeout / 2
            )

            upserted = db.upsert_articles(conn, articles, source_ids)

            try:
                races, drivers, teams = f1data.fetch_all(session, settings.f1_api_base, settings.http_timeout)
                details["races"] = db.upsert_races(conn, races)
                details["driver_standings"] = db.replace_driver_standings(conn, drivers)
                details["constructor_standings"] = db.replace_constructor_standings(conn, teams)
            except Exception as exc:  # noqa: BLE001
                status = "partial"
                details["errors"].append(f"f1-api: {exc}")
                log.warning("Falha na API de dados esportivos: %s", exc)

            details["purged"] = db.purge_old_articles(conn, settings.retention_days)

            if not articles:
                status = "failed"
        except Exception as exc:
            db.finish_run(conn, run_id, "failed", len(articles), 0, {**details, "fatal": repr(exc)})
            raise

        db.finish_run(conn, run_id, status, len(articles), upserted, details)
        log.info("Execução #%s: %s | %d manchetes processadas | %s", run_id, status, upserted, details)
        return 1 if status == "failed" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline de notícias de F1")
    parser.add_argument("--migrate-only", action="store_true", help="aplica só as migrações")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    return run(Settings.from_env(), migrate_only=args.migrate_only)


if __name__ == "__main__":
    sys.exit(main())
