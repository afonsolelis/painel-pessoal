# painel-pessoal · Painel F1

Página no GitHub Pages com as manchetes de Fórmula 1 do dia, em **português e inglês**.
Cada manchete leva à notícia original. Também mostra a próxima corrida (com contagem regressiva)
e as classificações de pilotos e construtores.

```
GitHub Actions (06h BRT) ──► pipeline Python ──► Supabase Postgres ──► index.html (GitHub Pages)
  10 feeds RSS + API Jolpica      normaliza, deduplica,       RLS: leitura      fetch na REST API
                                   upsert idempotente          pública           com chave publishable
```

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `pipeline/` | Coletor: RSS (`news.py`), calendário/classificação (`f1data.py`), banco (`db.py`) |
| `pipeline/sources.toml` | Catálogo de fontes — adicione uma fonte sem mexer em código |
| `db/migrations/` | Schema versionado (idempotente) |
| `index.html`, `assets/` | Front-end estático publicado no GitHub Pages |
| `.github/workflows/` | `collect-f1-data.yml` (diário), `ci.yml` (lint/testes/migrações), `deploy-pages.yml` |
| `docs/data-model.md` | Modelo de dados (diagrama ER) e decisões |

### Fontes

| Português | English |
|---|---|
| ge (Globo), Motorsport.com Brasil, Grande Prêmio, Autoracing | Autosport, Motorsport.com, BBC Sport, The Race, RaceFans, PlanetF1 |

Feeds que cobrem outras categorias (`f1_only = false`) passam por um filtro de palavras-chave de F1.
Artigos sem imagem no RSS recebem a `og:image` da página (limitado por execução).

## Configuração (uma vez)

1. **Segredo do banco**: *Settings → Secrets and variables → Actions → New repository secret*
   - Nome: `DATABASE_URL`
   - Valor: a connection string do Supabase (pooler, porta 6543)
2. **GitHub Pages**: *Settings → Pages*. Funciona com **Deploy from a branch** (`main`, `/ (root)`)
   ou com **GitHub Actions** (publica só `index.html` e `assets/`).
3. **Primeira carga**: *Actions → Coleta diária de F1 → Run workflow*.

A partir daí a coleta roda todo dia às 06h (09:00 UTC).

## Desenvolvimento local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && pytest
DATABASE_URL="postgresql://..." python -m pipeline        # coleta completa
DATABASE_URL="postgresql://..." python -m pipeline --migrate-only
python -m http.server 8000                       # front-end em http://localhost:8000
```

Variáveis opcionais: `MAX_ARTICLES_PER_SOURCE` (40), `MAX_ARTICLE_AGE_DAYS` (7),
`RETENTION_DAYS` (90), `LOG_LEVEL` (INFO).
