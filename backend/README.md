# Backend - RT-ROI

API FastAPI responsavel por ingestao, normalizacao e exposicao de metricas para o dashboard.

## Stack

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- httpx (integracao com RedTrack)

## Estrutura relevante

- `app/api/routes.py`
  - Endpoints HTTP do dashboard.
- `app/services/metrics_service.py`
  - Regras de agregacao e consultas.
- `app/services/filter_service.py`
  - Normalizacao e padronizacao de filtros.
- `app/services/redtrack/`
  - Pipeline, mapeamentos e sincronizacao com RedTrack.

## Endpoints principais

- `GET /metrics/summary`
- `GET /metrics/hourly/period`
- `GET /metrics/conversion-breakdown`
- `GET /metrics/charts/compare`
- `GET /health`

## Filtros suportados (geral)

- `period`
- `source` / `squad`
- `checkout`
- `product`
- `date_start`
- `date_end`

Comparacao de graficos:

- `base_date` (obrigatorio em `/metrics/charts/compare`)
- `compare_date` (obrigatorio em `/metrics/charts/compare`)

## Execucao local (via compose)

Na raiz do projeto:

```bash
docker compose up -d --build
```

## Observacoes

- O backend centraliza mapeamentos (checkout, squad, product) e aplica normalizacao antes de processar.
- Em caso de divergencia entre frontend e backend, validar payload bruto das rotas antes de ajustar UI.

