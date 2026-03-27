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
  python3 - <<'PY'
import urllib.request
urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', 'get-pip.py')
PY
  python3 get-pip.py
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

    stage('Gerar .env') {
      when {
        expression { params.RUN_DOCKER && fileExists('.env.example') }
      }
      steps {
        withCredentials([
          string(credentialsId: 'DATABASE_URL', variable: 'DATABASE_URL'),
          string(credentialsId: 'REDIS_URL', variable: 'REDIS_URL'),
          string(credentialsId: 'BACKEND_PORT', variable: 'BACKEND_PORT'),
          string(credentialsId: 'POSTGRES_USER', variable: 'POSTGRES_USER'),
          string(credentialsId: 'POSTGRES_PASSWORD', variable: 'POSTGRES_PASSWORD'),
          string(credentialsId: 'POSTGRES_DB', variable: 'POSTGRES_DB'),
          string(credentialsId: 'POSTGRES_HOST_PORT', variable: 'POSTGRES_HOST_PORT'),
          string(credentialsId: 'REDIS_HOST_PORT', variable: 'REDIS_HOST_PORT'),
          string(credentialsId: 'REDTRACK_API_KEY', variable: 'REDTRACK_API_KEY')
        ]) {
          sh '''#!/bin/sh
            set -eu

            cp .env.example .env

            sed -i "s|^DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env
            sed -i "s|^REDIS_URL=.*|REDIS_URL=$REDIS_URL|" .env
            sed -i "s|^BACKEND_PORT=.*|BACKEND_PORT=$BACKEND_PORT|" .env
            sed -i "s|^POSTGRES_USER=.*|POSTGRES_USER=$POSTGRES_USER|" .env
            sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" .env
            sed -i "s|^POSTGRES_DB=.*|POSTGRES_DB=$POSTGRES_DB|" .env
            sed -i "s|^POSTGRES_HOST_PORT=.*|POSTGRES_HOST_PORT=$POSTGRES_HOST_PORT|" .env
            sed -i "s|^REDIS_HOST_PORT=.*|REDIS_HOST_PORT=$REDIS_HOST_PORT|" .env
            sed -i "s|^REDTRACK_API_KEY=.*|REDTRACK_API_KEY=$REDTRACK_API_KEY|" .env

            echo ".env preparado com credenciais do Jenkins"
            '''
        }
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
