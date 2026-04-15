#!/bin/bash
set -e

# Aguardar PostgreSQL ficar pronto
echo "⏳ Aguardando PostgreSQL ficar disponível..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if python -c "
import os
import psycopg2
from sqlalchemy import create_engine

db_url = os.getenv('DATABASE_URL')
try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print('✅ PostgreSQL disponível!')
        exit(0)
except Exception as e:
    print(f'❌ Tentativa {$attempt}/{$max_attempts}: {e}')
    exit(1)
    " 2>/dev/null; then
        break
    fi

    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ PostgreSQL não ficou disponível após $max_attempts tentativas"
    exit 1
fi

# Rodar migrations
echo "🔄 Executando migrations..."
alembic upgrade head

# Iniciar aplicação
echo "🚀 Iniciando aplicação..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --timeout-keep-alive 120

