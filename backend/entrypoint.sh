#!/bin/bash
set -e

# Extrair host e porta do DATABASE_URL
# Exemplo: postgresql://user:pass@postgres:5432/db
DB_HOST=$(echo $DATABASE_URL | sed 's/.*@\([^:]*\).*/\1/')
DB_PORT=${DB_PORT:-5432}

echo "⏳ Aguardando PostgreSQL em $DB_HOST:$DB_PORT..."
max_attempts=60
attempt=1

while [ $attempt -le $max_attempts ]; do
    echo "   Tentativa $attempt/$max_attempts..."

    # Tentar conectar usando nc (netcat) ou python
    if command -v nc &> /dev/null; then
        # Se nc está disponível, usar isso
        if nc -z $DB_HOST $DB_PORT 2>/dev/null; then
            echo "✅ PostgreSQL disponível!"
            break
        fi
    else
        # Fallback para python
        if python3 -c "
import socket
import sys
try:
    socket.create_connection(('$DB_HOST', $DB_PORT), timeout=2)
    sys.exit(0)
except:
    sys.exit(1)
" 2>/dev/null; then
            echo "✅ PostgreSQL disponível!"
            break
        fi
    fi

    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ PostgreSQL não ficou disponível após $max_attempts tentativas"
    exit 1
fi

# Aguardar um pouco mais para ter certeza
sleep 3

# Rodar migrations
echo "🔄 Executando migrations..."
alembic upgrade head || echo "⚠️ Migrations já rodadas ou erro ao rodar"

# Iniciar aplicação
echo "🚀 Iniciando aplicação..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --timeout-keep-alive 120

