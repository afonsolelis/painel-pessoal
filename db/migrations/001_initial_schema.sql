-- =============================================================================
-- 001_initial_schema.sql
-- Modelo relacional do painel de Fórmula 1.
-- Idempotente: pode ser executado mais de uma vez sem efeitos colaterais.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Fontes de notícias (RSS)
-- -----------------------------------------------------------------------------
create table if not exists public.f1_sources (
    id          smallint generated always as identity primary key,
    slug        text        not null unique,
    name        text        not null,
    homepage    text        not null,
    feed_url    text        not null,
    language    text        not null check (language in ('pt', 'en')),
    is_active   boolean     not null default true,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

comment on table public.f1_sources is 'Portais de notícias de F1 coletados via RSS.';

-- -----------------------------------------------------------------------------
-- Notícias (manchetes)
-- -----------------------------------------------------------------------------
create table if not exists public.f1_articles (
    id            bigint generated always as identity primary key,
    source_id     smallint    not null references public.f1_sources (id) on delete cascade,
    url           text        not null unique,
    title         text        not null,
    summary       text,
    image_url     text,
    author        text,
    tags          text[]      not null default '{}',
    language      text        not null check (language in ('pt', 'en')),
    published_at  timestamptz not null,
    collected_at  timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

comment on table public.f1_articles is 'Manchetes de F1; a URL canônica garante unicidade (dedupe).';

create index if not exists f1_articles_published_at_idx
    on public.f1_articles (published_at desc);
create index if not exists f1_articles_language_published_idx
    on public.f1_articles (language, published_at desc);
create index if not exists f1_articles_source_idx
    on public.f1_articles (source_id);

-- -----------------------------------------------------------------------------
-- Calendário da temporada
-- -----------------------------------------------------------------------------
create table if not exists public.f1_races (
    season         smallint    not null,
    round          smallint    not null,
    race_name      text        not null,
    circuit_id     text        not null,
    circuit_name   text        not null,
    locality       text,
    country        text,
    race_start     timestamptz not null,
    qualifying_start timestamptz,
    sprint_start   timestamptz,
    wiki_url       text,
    updated_at     timestamptz not null default now(),
    primary key (season, round)
);

create index if not exists f1_races_race_start_idx on public.f1_races (race_start);

-- -----------------------------------------------------------------------------
-- Classificação de pilotos (snapshot mais recente por temporada)
-- -----------------------------------------------------------------------------
create table if not exists public.f1_driver_standings (
    season            smallint     not null,
    driver_id         text         not null,
    after_round       smallint     not null,
    position          smallint,
    driver_code       text,
    driver_number     text,
    given_name        text         not null,
    family_name       text         not null,
    nationality       text,
    constructor_name  text,
    points            numeric(6,1) not null default 0,
    wins              smallint     not null default 0,
    updated_at        timestamptz  not null default now(),
    primary key (season, driver_id)
);

-- -----------------------------------------------------------------------------
-- Classificação de construtores (snapshot mais recente por temporada)
-- -----------------------------------------------------------------------------
create table if not exists public.f1_constructor_standings (
    season          smallint     not null,
    constructor_id  text         not null,
    after_round     smallint     not null,
    position        smallint,
    name            text         not null,
    nationality     text,
    points          numeric(6,1) not null default 0,
    wins            smallint     not null default 0,
    updated_at      timestamptz  not null default now(),
    primary key (season, constructor_id)
);

-- -----------------------------------------------------------------------------
-- Auditoria das execuções do pipeline (privada)
-- -----------------------------------------------------------------------------
create table if not exists public.f1_pipeline_runs (
    id                bigint generated always as identity primary key,
    started_at        timestamptz not null default now(),
    finished_at       timestamptz,
    status            text        not null default 'running'
                      check (status in ('running', 'success', 'partial', 'failed')),
    articles_found    integer     not null default 0,
    articles_upserted integer     not null default 0,
    details           jsonb       not null default '{}'::jsonb,
    trigger           text
);

-- -----------------------------------------------------------------------------
-- updated_at automático
-- -----------------------------------------------------------------------------
create or replace function public.f1_touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

do $$
declare
    t text;
begin
    foreach t in array array['f1_sources', 'f1_articles', 'f1_races',
                             'f1_driver_standings', 'f1_constructor_standings']
    loop
        execute format('drop trigger if exists %I_touch on public.%I', t, t);
        execute format(
            'create trigger %I_touch before update on public.%I
             for each row execute function public.f1_touch_updated_at()', t, t);
    end loop;
end;
$$;

-- -----------------------------------------------------------------------------
-- View pública consumida pelo front-end
-- security_invoker => respeita as políticas RLS de quem consulta
-- -----------------------------------------------------------------------------
create or replace view public.f1_news_feed
with (security_invoker = true) as
select
    a.id,
    a.title,
    a.summary,
    a.url,
    a.image_url,
    a.language,
    a.tags,
    a.published_at,
    a.collected_at,
    s.slug  as source_slug,
    s.name  as source_name
from public.f1_articles a
join public.f1_sources  s on s.id = a.source_id;

-- -----------------------------------------------------------------------------
-- Segurança: RLS + somente leitura para clientes públicos
-- -----------------------------------------------------------------------------
alter table public.f1_sources               enable row level security;
alter table public.f1_articles              enable row level security;
alter table public.f1_races                 enable row level security;
alter table public.f1_driver_standings      enable row level security;
alter table public.f1_constructor_standings enable row level security;
alter table public.f1_pipeline_runs         enable row level security;

revoke all on public.f1_sources, public.f1_articles, public.f1_races,
              public.f1_driver_standings, public.f1_constructor_standings,
              public.f1_pipeline_runs, public.f1_news_feed
    from anon, authenticated;

grant select on public.f1_sources, public.f1_articles, public.f1_races,
                public.f1_driver_standings, public.f1_constructor_standings,
                public.f1_news_feed
    to anon, authenticated;

do $$
declare
    t text;
begin
    foreach t in array array['f1_sources', 'f1_articles', 'f1_races',
                             'f1_driver_standings', 'f1_constructor_standings']
    loop
        execute format('drop policy if exists "public read" on public.%I', t);
        execute format(
            'create policy "public read" on public.%I for select to anon, authenticated using (true)', t);
    end loop;
end;
$$;
-- f1_pipeline_runs fica sem política: acessível apenas pelo papel do pipeline.
