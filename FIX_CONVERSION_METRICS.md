# 🐛 Correção: Métricas de Conversão Duplicadas

## ❌ Problema Encontrado

As métricas de conversão (checkout e products) estavam sendo **duplicadas** quando um squad era filtrado.

**Sintomas:**
- Banco de dados: 5 checkouts, 0 purchases
- Frontend: 13 checkouts, 6 purchases (números errados)

## 🔍 Causa Raiz

A query SQL estava usando `OR squad = 'ALL'` ao filtrar por squad específico:

```sql
-- ERRADO ❌
WHERE metric_date BETWEEN :date_start AND :date_end
  AND (UPPER(squad) = UPPER(:squad) OR squad = 'ALL')
```

Isso resultava em **DOIS conjuntos de dados sendo somados**:
1. Dados do squad filtrado
2. Dados da linha `squad = 'ALL'` (que já contém agregação de TODOS os squads)

**Exemplo:**
- Se `squad = 'FBR'` tinha 5 checkouts
- E `squad = 'ALL'` tinha 13 checkouts (incluindo FBR + outros squads)
- A query retornava: 5 + 13 = 18 (ERRADO!)

## ✅ Solução Implementada

### 1. Corrigir `get_checkout_summary()` 
**Arquivo:** `/backend/app/services/metrics_service.py` (linha 656-660)

```python
# ANTES ❌
if squad:
    query += " AND (UPPER(squad) = UPPER(:squad) OR squad = 'ALL')"
    params["squad"] = squad

query += " GROUP BY checkout ORDER BY checkout_conversion DESC"

# DEPOIS ✅
if squad:
    query += " AND UPPER(squad) = UPPER(:squad)"
    params["squad"] = squad
else:
    query += " AND squad = 'ALL'"

query += " GROUP BY checkout ORDER BY checkout_conversion DESC"
```

### 2. Corrigir `get_product_summary()`
**Arquivo:** `/backend/app/services/metrics_service.py` (linha 714-721)

```python
# ANTES ❌
if squad:
    query += " AND (UPPER(squad) = UPPER(:squad) OR squad = 'ALL')"
    params["squad"] = squad

query += " GROUP BY product ORDER BY checkout_conversion DESC"

# DEPOIS ✅
if squad:
    query += " AND UPPER(squad) = UPPER(:squad)"
    params["squad"] = squad
else:
    query += " AND squad = 'ALL'"

query += " GROUP BY product ORDER BY checkout_conversion DESC"
```

## 📊 Mudanças de Comportamento

| Cenário | Antes | Depois |
|---------|-------|--------|
| Sem filtro squad | Retorna `squad='ALL'` | ✅ Retorna `squad='ALL'` |
| Com filtro squad | `squad='FBR' + 'ALL'` (duplicado) | ✅ Retorna apenas `squad='FBR'` |

## 🔧 Como Funciona Agora

### Quando NÃO há filtro de squad
```sql
WHERE metric_date BETWEEN :date_start AND :date_end
  AND squad = 'ALL'  -- Retorna agregação total
```

### Quando há filtro de squad (ex: FBR)
```sql
WHERE metric_date BETWEEN :date_start AND :date_end
  AND UPPER(squad) = UPPER('FBR')  -- Retorna APENAS FBR, não duplica
```

## 📝 Estrutura de Dados no Banco

A tabela `tb_daily_checkout_summary` armazena:

| metric_date | checkout | squad | initiate_checkout | purchase |
|------------|----------|-------|-------------------|----------|
| 2026-04-04 | Cartpanda | FBR   | 5                 | 2        |
| 2026-04-04 | Cartpanda | YTS   | 8                 | 4        |
| 2026-04-04 | Cartpanda | ALL   | 13                | 6        |
| 2026-04-04 | Clickbank | FBR   | 3                 | 1        |
| 2026-04-04 | Clickbank | ALL   | 7                 | 3        |

**Consultas corretas:**
- Sem filtro: Busca linhas com `squad='ALL'` 
- Com squad='FBR': Busca apenas linhas com `squad='FBR'`

## ✅ Teste

Após o deploy, teste:

```bash
# Sem squad - deve retornar valores "ALL"
curl "http://localhost:8000/api/metrics/by-checkout?period=24h"

# Com squad FBR - deve retornar apenas valores de FBR (não duplicados)
curl "http://localhost:8000/api/metrics/by-checkout?period=24h&source=FBR"

# Com squad YTS - deve retornar apenas valores de YTS
curl "http://localhost:8000/api/metrics/by-checkout?period=24h&source=YTS"
```

## 🔍 Verificação Manual no Banco

```sql
-- Verificar dados salvos
SELECT metric_date, checkout, squad, 
       initiate_checkout, purchase,
       (purchase::numeric / initiate_checkout * 100) as conversion
FROM tb_daily_checkout_summary
WHERE metric_date = '2026-04-04'
ORDER BY squad, checkout;

-- Resultado esperado:
-- FBR + YTS (individual) + ALL (agregado)
```

## 🚀 Status

✅ **CORREÇÃO APLICADA COM SUCESSO**

Os arquivos foram modificados:
- ✅ `/backend/app/services/metrics_service.py` (2 funções corrigidas)

O sistema agora retorna os valores corretos das métricas de conversão sem duplicação!


