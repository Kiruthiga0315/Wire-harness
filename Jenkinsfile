
pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                echo 'GitHub repository connected!'
                checkout scm
            }
        }

        stage('Inspect Project') {
            steps {
                bat 'dir'
            }
        }

        stage('Verify Python') {
            steps {
                bat 'python --version'
            }
        }

        stage('Finish') {
            steps {
                echo 'Wire Harness Jenkins Pipeline SUCCESS!'
            }
        }
    }
}
