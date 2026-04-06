# RT-ROI Dashboard

Dashboard de performance com ingestao de dados do RedTrack, backend FastAPI e frontend React.

## Visao geral

- Objetivo: acompanhar custo, receita, lucro, checkout e ROI com filtros centralizados.
- Frontend: React + Vite + Recharts.
- Backend: FastAPI + SQLAlchemy + Alembic.
- Dados: PostgreSQL (persistencia) + Redis (cache).
- Infra: Docker Compose (frontend, backend, db, redis, cron).

## Arquitetura

```text
Frontend (React) -> /api -> Backend (FastAPI) -> PostgreSQL
                                  |
                                  +-> Redis
                                  +-> RedTrack API (pipeline/sincronizacao)
```

## Estrutura principal

- `backend/`: API, servicos, modelos e migracoes.
- `frontend/`: dashboard, filtros globais e graficos.
- `docker-compose.yml`: sobe ambiente completo local.
- `backend/app/services/redtrack/`: pipeline de ingestao e normalizacao.

## Como rodar (local)

```bash
docker compose up -d --build
```

Acessos comuns:

- Frontend: `http://localhost`
- API (via proxy): `http://localhost/api`
- Docs da API: `http://localhost/api/docs`

## Filtros suportados

Filtros principais usados no sistema:

- `period`
- `source` / `squad`
- `checkout`
- `product`
- `date_start`
- `date_end`

No frontend, os filtros ficam centralizados no contexto e refletem nas requisicoes.

## Endpoints principais (fase atual)

- `GET /metrics/summary`
  - Cards principais (hoje, ontem e comparacao).
- `GET /metrics/hourly/period`
  - Serie horaria para grafico principal.
  - Aceita filtros e intervalo por data.
- `GET /metrics/conversion-breakdown`
  - Conversao por squad/checkout/produto.
  - Aceita filtros e intervalo por data.
- `GET /metrics/charts/compare`
  - Compara duas datas para os graficos.
  - Query obrigatoria: `base_date`, `compare_date`.
- `GET /health`
  - Healthcheck basico.

## Fluxo de dados resumido

1. Pipeline coleta dados do RedTrack.
2. Backend normaliza e persiste no banco.
3. Frontend consome endpoints filtrados.
4. Graficos podem comparar dia base vs dia comparado.

## Documentacao por camada

- Frontend: `frontend/README.md`
- Backend: `backend/README.md`

## Observacoes

- O projeto esta em evolucao continua de mapeamentos, filtros e qualidade de dados.
- Em caso de divergencia visual, validar payload retornado pelos endpoints da API primeiro.
