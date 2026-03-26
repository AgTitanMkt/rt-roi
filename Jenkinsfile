pipeline {
  agent any

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
          sh 'python3 --version'
          sh 'python3 -m venv .venv'
          sh '. .venv/bin/activate && pip install --upgrade pip'
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

    stage('Docker Compose Check') {
      when {
        expression { fileExists('docker-compose.yml') }
      }
      steps {
        sh 'docker compose config -q'
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
