pipeline {
  agent any

  parameters {
    booleanParam(name: 'RUN_DOCKER', defaultValue: true, description: 'Sobe servicos com docker compose no final da pipeline')
  }

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    PIP_CACHE_DIR = "${WORKSPACE}/.pip-cache"
    NPM_CONFIG_CACHE = "${WORKSPACE}/.npm-cache"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Backend CI') {
      steps {
        dir('backend') {
          sh '''#!/bin/sh
set -eu

python3 --version

# Some Debian/Ubuntu Jenkins agents do not ship ensurepip (python3-venv missing).
if python3 -m venv .venv; then
  echo "venv created with ensurepip"
else
  echo "python3 -m venv failed; trying fallback without ensurepip"
  rm -rf .venv
  python3 -m venv --without-pip .venv
  . .venv/bin/activate
  python - <<'PY'
import urllib.request
urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', 'get-pip.py')
PY
  python get-pip.py
  rm -f get-pip.py
fi
'''
          sh '. .venv/bin/activate && python -m pip install --upgrade pip'
          sh '. .venv/bin/activate && pip install -r requirements.txt'
          sh '. .venv/bin/activate && python -m compileall -q app'
        }
      }
    }

    stage('Frontend CI') {
      steps {
        dir('frontend') {
          sh 'node --version'
          sh 'npm --version'
          sh 'npm ci'
          sh 'npm run lint'
          sh 'npm run build'
        }
      }
    }

    stage('Prepare Dotenv') {
      when {
        expression { params.RUN_DOCKER && fileExists('.env.example') }
      }
      steps {
        sh '''#!/bin/sh
set -eu

cp .env.example .env

upsert_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    awk -v k="$key" -v v="$value" 'BEGIN {FS=OFS="="} $1==k {$0=k"="v} {print}' .env > .env.tmp
    mv .env.tmp .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

[ -n "${DATABASE_URL:-}" ] && upsert_env DATABASE_URL "$DATABASE_URL"
[ -n "${REDIS_URL:-}" ] && upsert_env REDIS_URL "$REDIS_URL"
[ -n "${BACKEND_PORT:-}" ] && upsert_env BACKEND_PORT "$BACKEND_PORT"
[ -n "${POSTGRES_USER:-}" ] && upsert_env POSTGRES_USER "$POSTGRES_USER"
[ -n "${POSTGRES_PASSWORD:-}" ] && upsert_env POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
[ -n "${POSTGRES_DB:-}" ] && upsert_env POSTGRES_DB "$POSTGRES_DB"
[ -n "${POSTGRES_HOST_PORT:-}" ] && upsert_env POSTGRES_HOST_PORT "$POSTGRES_HOST_PORT"
[ -n "${REDIS_HOST_PORT:-}" ] && upsert_env REDIS_HOST_PORT "$REDIS_HOST_PORT"

# Keep backend and cron compatible even if Jenkins only sets one key name.
if [ -n "${REDTRACK_API_KEY:-}" ]; then
  upsert_env REDTRACK_API_KEY "$REDTRACK_API_KEY"
  upsert_env REDTRACK_KEY "$REDTRACK_API_KEY"
fi
if [ -n "${REDTRACK_KEY:-}" ]; then
  upsert_env REDTRACK_KEY "$REDTRACK_KEY"
  upsert_env REDTRACK_API_KEY "$REDTRACK_KEY"
fi

echo ".env preparado a partir do .env.example"
'''
      }
    }

    stage('Docker Compose Up') {
      when {
        expression { params.RUN_DOCKER && fileExists('docker-compose.yml') }
      }
      steps {
        sh 'docker version'
        sh 'docker compose version'
        sh 'docker compose config -q'
        sh 'docker compose up -d --build'
        sh 'docker compose ps'
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'frontend/dist/**', allowEmptyArchive: true
      cleanWs(deleteDirs: true)
    }
  }
}
