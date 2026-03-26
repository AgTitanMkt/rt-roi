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

    stage('Gerar .env') {
            steps {
                withCredentials([
                    string(credentialsId: 'REDTRACK_API_KEY', variable: 'REDTRACK_API_KEY'),

                    string(credentialsId: 'DATABASE_URL', variable: 'DATABASE_URL'),
                    string(credentialsId: 'POSTGRESS_USER', variable: 'POSTGRESS_USER'),
                    string(credentialsId: 'POSTGRESS_PASSWORD', variable: 'POSTGRESS_PASSWORD'),

                    string(credentialsId: 'REDIS_URL', variable: 'REDIS_URL'),
                    string(credentialsId: 'POSTGRES_DB', variable: 'POSTGRES_DB'),

                    string(credentialsId: 'POSTGRES_HOST_PORT', variable: 'POSTGRES_HOST_PORT'),
                    string(credentialsId: 'REDIS_HOST_PORT', variable: 'REDIS_HOST_PORT'),
                ]) {
                    sh '''
                    cp .env.example .env

                    sed -i "s|REDTRACK_API_KEY=.*|REDTRACK_API_KEY=$REDTRACK_API_KEY|" .env

                    sed -i "s|DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env
                    sed -i "s|POSTGRESS_USER=.*|POSTGRESS_USER=$POSTGRESS_USER|" .env
                    sed -i "s|POSTGRESS_PASSWORD=.*|POSTGRESS_PASSWORD=$POSTGRESS_PASSWORD|" .env

                    sed -i "s|REDIS_URL=.*|REDIS_URL=$REDIS_URL|" .env
                    sed -i "s|POSTGRES_DB=.*|POSTGRES_DB=$POSTGRES_DB|" .env

                    sed -i "s|POSTGRES_HOST_PORT=.*|POSTGRES_HOST_PORT=$POSTGRES_HOST_PORT|" .env
                    sed -i "s|REDIS_HOST_PORT=.*|REDIS_HOST_PORT=$REDIS_HOST_PORT|" .env

                    echo "APP_URL=https://roi.agenciatitandev.com" >> .env
                    '''
                }
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
