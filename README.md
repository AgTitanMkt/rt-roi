# 📊 Dashboard RedTrack (React + FastAPI + PostgreSQL)

## 🚀 Visão Geral

Este projeto é um dashboard para visualização de métricas de campanhas (Revenue, Cost, Profit e ROI) consumindo dados da API do RedTrack.

A aplicação foi construída com foco em:

* Performance
* Escalabilidade
* Facilidade de evolução

---

## 🧱 Stack Utilizada

### Frontend

* React
* Vite
* React query (requisições HTTP)
* Recharts (gráficos)

### Backend

* FastAPI
* httpx (requisições async)
* SQLModel
* Alembic
* Pydantic

### Banco de Dados

* PostgreSQL

### Cache

* Redis

### Infra

* Docker + Docker Compose
* Nginx (gateway)

---

## 🧠 Arquitetura

```
React → Nginx → FastAPI → PostgreSQL
                      ↓
                    Redis
                      ↓
                 RedTrack API
```

### Regras importantes:

* O frontend nunca acessa o RedTrack diretamente
* Toda lógica fica no backend
* O backend é responsável por:
  * Buscar dados
  * Cachear
  * Persistir

---

## 📊 Funcionalidades

* KPIs principais:
  * Revenue
  * Cost
  * Profit
  * ROI

* Gráfico:
  * Revenue vs Cost por hora

* Filtros:
  * Intervalo de datas
  * Campanha (futuro)

---

## ⚙️ Funcionamento

O sistema funciona sob demanda:

1. Frontend chama `/dashboard`
2. Backend verifica:
   * Existe dado recente no cache?
     * Sim → retorna
     * Não → verifica banco
     
3. Se banco estiver desatualizado:
   * Busca dados no RedTrack
   * Salva no banco
   * Atualiza cache
   
4. Retorna resposta

---

## ⏱️ Estratégia de Cache

* TTL padrão: 5 minutos
* Redis é sempre a primeira fonte
* Banco é fallback
* RedTrack é última opção

---

## 🗄️ Banco de Dados

### Tabela principal: `metrics_hourly`

```sql
CREATE TABLE metrics_hourly (
    id SERIAL PRIMARY KEY,
    datetime TIMESTAMP NOT NULL,
    campaign_id TEXT,
    revenue NUMERIC,
    cost NUMERIC,
    profit NUMERIC,
    roi NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(datetime, campaign_id)
);
```

---

## 🔌 Endpoint principal

### Endpoints Principais

#### `GET /metrics/summary`

Retorna os KPIs agregados (custo total, lucro total e ROI) de todas as fontes.

**Query Parameters:**
- `source` (opcional): Filtra por origem de tráfego (ex: `mediago`, `google`, `facebook`)

**Exemplo de resposta:**
```json
{
  "cost": 169.21,
  "profit": 60.79,
  "roi": 0.36
}
```

---

#### `GET /metrics/hourly`

Retorna uma série temporal por hora com custo, lucro e ROI agregados. Filtra automaticamente apenas as horas de **hoje**.

**Query Parameters:**
- `source` (opcional): Filtra por origem de tráfego (ex: `mediago`, `google`, `facebook`)

**Exemplo de resposta:**
```json
[
  {
    "hour": "14",
    "cost": 12.1,
    "profit": 4.2,
    "roi": 0.35
  },
  {
    "hour": "15",
    "cost": 10.4,
    "profit": 3.1,
    "roi": 0.30
  }
]
```

---

### Endpoints de Saúde

#### `GET /health`

Verifica a disponibilidade geral da API.

---

#### `GET /health/db`

Verifica a conexão com o banco de dados PostgreSQL.

---

## 📚 Documentação Interativa (Swagger)

A API inclui documentação interativa automática gerada pelo **Swagger UI** e **ReDoc**.

**Acesso:**
- Swagger UI: `/docs`
- ReDoc: `/redoc`

Nesta interface você pode:
- ✅ Ver todos os endpoints disponíveis
- ✅ Testar requisições diretamente no navegador
- ✅ Consultar esquemas de requisição e resposta
- ✅ Verificar exemplos de respostas para cada endpoint

**Exemplo de URL local:**
```
http://localhost:8000/docs
```


---

## 🐳 Como rodar o projeto

### 1. Clonar repositório

```bash
git clone <repo>
cd project
```

### 2. Subir containers

```bash
docker compose up -d --build
```

---

## 🌐 Rotas

* `/` → Frontend (React)
* `/api` → Backend (FastAPI)

---

## 📌 Objetivo do projeto

Construir um dashboard rápido, confiável e pronto para escalar sem precisar refatorar toda a base no futuro.

---

## Jenkins (pipeline inicial)

O repositório agora inclui um `Jenkinsfile` na raiz com uma pipeline CI inicial para:

- Backend (`backend/`): criar venv, instalar dependências e validar sintaxe com `compileall`
- Frontend (`frontend/`): `npm ci`, `npm run lint` e `npm run build`
- Infra: validação de `docker-compose.yml` com `docker compose config -q`

### Pré-requisitos no agente Jenkins

- Git
- Python 3
- Node.js 20+ e npm
- Docker CLI + plugin Compose (para o estágio de Docker)

### Como criar o job

1. No Jenkins, crie um novo item do tipo **Pipeline**.
2. Em **Pipeline Definition**, selecione **Pipeline script from SCM**.
3. Configure o repositório Git deste projeto.
4. Mantenha `Jenkinsfile` como **Script Path**.
5. Salve e execute o build.

> Observação: se o agente não tiver Docker disponível, remova temporariamente o estágio `Docker Compose Check` do `Jenkinsfile`.
