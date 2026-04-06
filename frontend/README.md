# Frontend - RT-ROI

Aplicacao React responsavel por exibir cards, graficos e filtros globais do dashboard.

## Stack

- React + TypeScript
- Vite
- Recharts

## Scripts

```bash
npm install
npm run dev
npm run build
npm run lint
```

## Estrutura relevante

- `src/context/FilterContext.tsx`
  - Estado global de filtros.
  - Estado de comparacao de datas para graficos.
- `src/hooks/useFilteredData.ts`
  - Orquestra requisicoes da API.
  - Consome dados normais e comparativos.
- `src/componentes/FilterBar.tsx`
  - Barra unica de filtros.
- `src/componentes/DashboardGrafico1.tsx`
  - Grafico horario principal (com comparacao base vs comparado).
- `src/componentes/ConversionInsightsChart.tsx`
  - Grafico de conversao.
- `src/utils/reqs.ts`
  - Cliente HTTP e contratos dos endpoints.

## Filtros

Filtros aplicados no frontend:

- `period`
- `squad`
- `checkout`
- `product`
- `date_start`
- `date_end`

Comparacao de graficos:

- `compare_enabled`
- `compare_base_date`
- `compare_target_date`

Esses dados tambem sao sincronizados na URL para manter estado no reload.

## Integracao com API

Principais chamadas usadas:

- `/api/metrics/summary`
- `/api/metrics/hourly/period`
- `/api/metrics/conversion-breakdown`
- `/api/metrics/charts/compare`
- `/api/health`

## Observacao

Quando houver divergencia visual nos graficos, validar primeiro os dados retornados pela API no navegador (Network) e no backend.
