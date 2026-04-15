FROM python:3.11-slim

# Evita cache e melhora logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar netcat para health checks
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Expose port
EXPOSE 8000

# Run with entrypoint script (sem changear user para que possa conectar ao DB durante init)
ENTRYPOINT ["./entrypoint.sh"]
