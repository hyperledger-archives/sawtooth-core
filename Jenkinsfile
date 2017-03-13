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

        if (!(env.BRANCH_NAME == 'master' && env.JOB_BASE_NAME == 'master')) {
            stage("Check Whitelist") {
                readTrusted 'bin/whitelist'
                readTrusted 'MAINTAINERS'
                sh './bin/whitelist "$CHANGE_AUTHOR" MAINTAINERS'
            }
        }

        stage("Check for Signed-Off Commits") {
            sh '''#!/bin/bash -l
                if [ -v CHANGE_URL ] ;
                then
                    temp_url="$(echo $CHANGE_URL |sed s#github.com/#api.github.com/repos/#)/commits"
                    pull_url="$(echo $temp_url |sed s#pull#pulls#)"

                    IFS=$'\n'
                    for m in $(curl -s "$pull_url" | grep "message") ; do
                        if echo "$m" | grep -qi signed-off-by:
                        then
                          continue
                        else
                          echo "FAIL: Missing Signed-Off Field"
                          echo "$m"
                          exit 1
                        fi
                    done
                    unset IFS;
                fi
            '''
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
            sh 'docker build . -f docker/sawtooth-build-java -t sawtooth-build-java:$BUILD_TAG'
            sh 'docker run -v $(pwd):/project/sawtooth-core sawtooth-build-java:$BUILD_TAG'
            sh 'docker build . -f docker/sawtooth-build-javascript -t sawtooth-build-javascript:$BUILD_TAG'
            sh 'docker run -v $(pwd):/project/sawtooth-core sawtooth-build-javascript:$BUILD_TAG'
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
                        REPO=$(git remote show -n origin | grep Fetch | awk -F'[/.]' '{print $6}')
                        VERSION=`git describe --dirty`
                        git archive HEAD --format=zip -9 --output=$REPO-$VERSION.zip
                        git archive HEAD --format=tgz -9 --output=$REPO-$VERSION.tgz
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
