FROM python:3.11-slim

WORKDIR /app

ENV TZ=America/Sao_Paulo

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend .

# instala cron + timezone
RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata \
	&& ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
	&& echo $TZ > /etc/timezone \
	&& rm -rf /var/lib/apt/lists/*

# copia crontab
COPY docker/cron/crontab /etc/cron.d/my-cron

# permissões
RUN chmod 0644 /etc/cron.d/my-cron

# cria log
RUN touch /var/log/cron.log

CMD ["sh", "-lc", "printenv > /etc/environment && cron -f"]