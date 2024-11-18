pipeline {
  agent any

  environment {
    DOCKER_CRED = credentials('docker-hub-credentials')
  }

  stages {
    stage('Build') {
      steps {
       sh '''#!/bin/bash
       #Backend Build
        python3.9 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r backend/requirements.txt
        
        # Frontend Build
        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
        sudo apt-get install -y nodejs
        cd ./frontend
        export NODE_OPTIONS=--openssl-legacy-provider
        export CI=false
        npm ci
        '''
      }
    }
    
    stage('Test') {
      steps {
        sh '''#!/bin/bash
        source venv/bin/activate
        pip install pytest-django
        python backend/manage.py makemigrations
        python backend/manage.py migrate
        pytest backend/account/tests.py --verbose --junit-xml test-reports/results.xml
        '''
      }
    }

    stage('Cleanup') {
      agent { label 'build-node' }
      steps {
        sh '''#!/bin/bash
        # Only clean Docker system
        docker system prune -f
        
        # Safer git clean that preserves terraform state
        git clean -ffdx -e "*.tfstate*" -e ".terraform/*"
        '''
      }
    }

    stage('Build & Push Images') {
      agent { label 'build-node' }
      steps {
        sh '''
        echo ${DOCKER_CRED_PSW} | docker login -u ${DOCKER_CRED_USR} --password-stdin
        '''
        
        // Build and push backend
        sh '''#!/bin/bash
        docker build -t tortiz7/ecommerce-backend-image:latest -f Dockerfile.backend .
        docker push tortiz7/ecommerce-backend-image:latest
        '''
        
        // Build and push frontend
        sh '''#!/bin/bash
        docker build -t tortiz7/ecommerce-frontend-image:latest -f Dockerfile.frontend .
        docker push tortiz7/ecommerce-frontend-image:latest
        '''
      }
    }

    stage('Infrastructure') {
      agent { label 'build-node' }
      steps {
        dir('Terraform') {
          withCredentials([file(credentialsId: 'tf_vars', variable: 'TFVARS')]) {
            sh '''#!/bin/bash
            terraform init
            terraform apply -auto-approve -var-file=${TFVARS} \
              -var="dockerhub_username=${DOCKER_CRED_USR}" \
              -var="dockerhub_password=${DOCKER_CRED_PSW}"
            '''
          }
        }
      }
    }
  }

  post {
    always {
      agent { label 'build-node' }
      steps {
        sh '''#!/bin/bash
        docker logout
        docker system prune -f
        '''
      }
    }
  }
}
