# Modelagem de dados

Banco: Postgres do Supabase, schema `public`, tabelas com prefixo `f1_`.
Migrações versionadas em [`db/migrations`](../db/migrations), aplicadas automaticamente pelo pipeline
(controle em `f1_schema_migrations`).

```mermaid
erDiagram
    f1_sources ||--o{ f1_articles : publica
    f1_sources {
        smallint id PK
        text slug UK
        text name
        text homepage
        text feed_url
        text language "pt | en"
        boolean is_active
    }
    f1_articles {
        bigint id PK
        smallint source_id FK
        text url UK "URL canônica (dedupe)"
        text title
        text summary
        text image_url
        text author
        text_array tags
        text language "pt | en"
        timestamptz published_at
        timestamptz collected_at
    }
    f1_races {
        smallint season PK
        smallint round PK
        text race_name
        text circuit_id
        text circuit_name
        text locality
        text country
        timestamptz race_start
        timestamptz qualifying_start
        timestamptz sprint_start
    }
    f1_driver_standings {
        smallint season PK
        text driver_id PK
        smallint after_round
        smallint position
        text given_name
        text family_name
        text constructor_name
        numeric points
        smallint wins
    }
    f1_constructor_standings {
        smallint season PK
        text constructor_id PK
        smallint after_round
        smallint position
        text name
        numeric points
        smallint wins
    }
    f1_pipeline_runs {
        bigint id PK
        timestamptz started_at
        timestamptz finished_at
        text status "running | success | partial | failed"
        int articles_found
        int articles_upserted
        jsonb details
    }
```

## Decisões

| Decisão | Motivo |
|---|---|
| `f1_articles.url` único, após remover `utm_*`, `at_*` e fragmentos | Deduplicação entre execuções; `upsert` idempotente |
| `language` na fonte **e** no artigo | Filtro rápido por idioma com índice `(language, published_at desc)` |
| View `f1_news_feed` com `security_invoker` | O front faz uma única consulta e as políticas RLS continuam valendo |
| Classificações como *snapshot* por `(season, id)` | O painel mostra só a tabela atual; `after_round` indica a etapa |
| `f1_pipeline_runs` sem política RLS | Auditoria privada: o papel `anon` não lê nem escreve |
| Retenção de 90 dias (`RETENTION_DAYS`) | Mantém o banco pequeno no plano gratuito |

## Segurança

- RLS ativo em todas as tabelas; `anon`/`authenticated` têm apenas `SELECT` nas tabelas públicas.
- A chave *publishable* usada no `index.html` é pública por design; a escrita só acontece pelo
  pipeline, com a `DATABASE_URL` guardada como segredo do GitHub Actions.
