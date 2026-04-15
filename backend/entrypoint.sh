#!/bin/bash
set -e

# Extrair host e porta do DATABASE_URL com mais precisão
# Exemplos suportados:
# - postgresql://user:pass@postgres:5432/db
# - postgresql://user:pass@localhost:5433/db
# - postgresql://user@host/db (usa porta padrão 5432)

if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL não está definida!"
    exit 1
fi

# Extrair host (nome do host ou IP após @)
DB_HOST=$(echo "$DATABASE_URL" | sed 's|.*@\([^:/]*\).*|\1|')

# Extrair porta (número após o primeiro : do host, antes de / ou fim da string)
# Se não houver porta explícita, usar 5432
if echo "$DATABASE_URL" | grep -q "@[^/]*:[0-9]"; then
    DB_PORT=$(echo "$DATABASE_URL" | sed 's|.*@[^:]*:\([0-9]*\).*|\1|')
else
    DB_PORT=5432
fi

# Se DB_PORT estiver vazio, usar padrão
if [ -z "$DB_PORT" ] || [ "$DB_PORT" = "$DATABASE_URL" ]; then
    DB_PORT=5432
fi

echo "⏳ Aguardando PostgreSQL em $DB_HOST:$DB_PORT..."
echo "📋 DATABASE_URL: $(echo $DATABASE_URL | sed 's/:\/\/.*@/:\/\/***@/' | sed 's/@.*:/@...:/') "
max_attempts=60
attempt=1

while [ $attempt -le $max_attempts ]; do
    echo "   Tentativa $attempt/$max_attempts..."

    # Tentar conectar usando nc (netcat) ou python
    if command -v nc &> /dev/null; then
        # Se nc está disponível, usar isso
        if nc -z -w 2 $DB_HOST $DB_PORT 2>/dev/null; then
            echo "✅ PostgreSQL disponível em $DB_HOST:$DB_PORT!"
            break
        fi
    else
        # Fallback para python
        if python3 -c "
import socket
import sys
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('$DB_HOST', int($DB_PORT)))
    sock.close()
    if result == 0:
        sys.exit(0)
    else:
        sys.exit(1)
except Exception as e:
    print(f'Erro: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
            echo "✅ PostgreSQL disponível em $DB_HOST:$DB_PORT!"
            break
        fi
    fi

    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ PostgreSQL não ficou disponível após $max_attempts tentativas em $DB_HOST:$DB_PORT"
    echo "❌ Verifique:"
    echo "   - Se o PostgreSQL está rodando"
    echo "   - Se o host '$DB_HOST' é acessível"
    echo "   - Se a porta $DB_PORT está correta"
    echo "   - Se há firewall bloqueando a conexão"
    exit 1
fi

# Aguardar um pouco mais para ter certeza que a conexão está estável
sleep 3

# Rodar migrations
echo "🔄 Executando migrations..."
alembic upgrade head || echo "⚠️ Migrations já rodadas ou erro ao rodar"

# Iniciar aplicação
echo "🚀 Iniciando aplicação..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --timeout-keep-alive 120

