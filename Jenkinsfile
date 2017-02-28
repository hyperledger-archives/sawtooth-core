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

// Discard old builds after 31 days
properties([[$class: 'BuildDiscarderProperty', strategy:
        [$class: 'LogRotator', artifactDaysToKeepStr: '',
        artifactNumToKeepStr: '', daysToKeepStr: '31', numToKeepStr: '']]]);

node ('master') {
    // Create a unique workspace so Jenkins doesn't reuse an existing one
    ws("workspace/${env.BUILD_TAG}") {

        stage("Clone Repo") {
            checkout scm
        }
        stage("Verify Scripts") {
            readTrusted 'bin/build_all'
            readTrusted 'bin/run_tests'
            readTrusted 'bin/run_lint'
            readTrusted 'bin/docker_build_all'
            readTrusted 'bin/run_docker_test'
            readTrusted 'bin/protogen'
            readTrusted 'cli/setup.py'
            readTrusted 'rest_api/setup.py'
            readTrusted 'sdk/python/setup.py'
            readTrusted 'signing/setup.py'
            readTrusted 'validator/setup.py'
        }

        // Use a docker container to build and protogen, so that the Jenkins
        // environment doesn't need all the dependencies.
        stage("Build Test Dependencies") {
            docker.build('sawtooth-build:$BUILD_TAG', '-f docker/sawtooth-build-ubuntu-xenial .')
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh './bin/build_all'
                }
            }
        }

        stage("Run Lint") {
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh './bin/run_lint'
                }
            }
        }

        // Run the tests
        stage("Run Tests") {
            // Required docker containers are built by the tests
            sh './bin/docker_build_all -p $(printf $BUILD_TAG | sha256sum | cut -c1-64)'
            sh './bin/run_tests -p $(printf $BUILD_TAG | sha256sum | cut -c1-64)'
        }

        stage("Create git archive") {
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh '''
                        NAME=`git describe --dirty`
                        REPONAME=$(git remote show -n origin | grep Fetch | awk -F'[/.]' '{print $6}')
                        git archive HEAD --prefix=$REPONAME-$NAME --format=zip -9 --output=$REPONAME-$NAME.zip
                        git archive HEAD --prefix=$REPONAME-$NAME --format=tgz -9 --output=$REPONAME-$NAME.tgz
                    '''
                }
            }
        }

        stage("Build the packages"){
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh 'VERSION=AUTO_STRICT ./bin/build_debs'
                    stash name: 'debs', includes: 'build/debs/*.deb'
                }
            }
        }

        stage("Build docker docs build slave") {
            sh 'sed -i\'\' -e"s/@@BUILD_TAG@@/$BUILD_TAG/" ci/sawtooth-docker-test'
            docker.build('sawtooth-docs:$BUILD_TAG', '-f ci/sawtooth-docker-test .')
        }

        stage ("Build documentation") {
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-docs:$BUILD_TAG').inside {
                    sh 'cd docs && make html latexpdf'
                }
            }
        }

        stage("Remove docker images") {
            sh 'docker rmi sawtooth-build:$BUILD_TAG'
            sh 'docker rmi sawtooth-docs:$BUILD_TAG'
        }

        stage("Archive Build artifacts") {
            archiveArtifacts artifacts: '*.tgz, *.zip'
            archiveArtifacts artifacts: 'build/debs/*.deb'
            archiveArtifacts artifacts: 'docs/build/html/**, docs/build/latex/*.pdf'
        }
    }
}
