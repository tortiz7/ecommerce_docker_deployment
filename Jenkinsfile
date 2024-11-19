pipeline {
  agent any

  environment {
    DOCKER_CRED = credentials('docker-hub-credentials')
    private_ip = "172.31.39.47"
  }

  stages {
    stage('Build') {
      steps {
        sh '''#!/bin/bash
        # Clean old / corrupt APT cache

        sudo rm -rf /var/lib/apt/lists/*
        sudo apt-get clean
        sudo apt-get update

        # Build Frontend

        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
        sudo apt install -y nodejs
        cd frontend
        sed -i "s|http://private_ec2_ip:8000|http://${private_ip}:8000|" package.json
        npm i
        export NODE_OPTIONS=--openssl-legacy-provider
        npm start &

        # Build Backend
        cd ..
        sudo add-apt-repository ppa:deadsnakes/ppa -y
        sudo apt update -y
        sudo apt install -y python3.9 python3.9-venv python3.9-dev python3-pip
        python3.9 -m venv venv
        source venv/bin/activate
        pip install -r backend/requirements.txt
        python3 backend/manage.py runserver 0.0.0.0:8000 &
        '''
      }
    }
    
    stage('Test') {
      steps {
        sh '''#!/bin/bash
        python3.9 -m venv venv
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
        # Cleanup Docker system
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
        
        script {
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
    }

    stage('Infrastructure') {
      agent { label 'build-node' }
      steps {
        dir('Terraform') {
          withCredentials([file(credentialsId: 'tf_vars', variable: 'TFVARS')]) {
            sh '''#!/bin/bash
            terraform init
            terraform apply -auto-approve -var-file=${TFVARS}
            '''
          }
        }
      }
    }
  }

  post {
    always {
      steps {
        sh '''#!/bin/bash
        # Final Docker cleanup and logout
        docker logout
        docker system prune -f
        '''
      }
    }
  }
}
