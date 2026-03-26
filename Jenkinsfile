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
