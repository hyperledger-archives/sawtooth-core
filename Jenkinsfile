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

        // Set the ISOLATION_ID environment variable for the whole pipeline
        env.ISOLATION_ID = sh(returnStdout: true, script: 'printf $BUILD_TAG | sha256sum | cut -c1-64').trim()

        // Use a docker container to build and protogen, so that the Jenkins
        // environment doesn't need all the dependencies.
        stage("Build Test Dependencies") {
            sh './bin/build_all'
        }

        stage("Run Lint") {
            sh 'docker run --rm -v $(pwd):/project/sawtooth-core sawtooth-build-python:$ISOLATION_ID ./bin/run_lint'
        }

        stage("Run Bandit") {
            sh 'docker run --rm -v $(pwd):/project/sawtooth-core sawtooth-build-python:$ISOLATION_ID ./bin/run_bandit || $TRUE'
        }

        // Run the tests
        stage("Run Tests") {
            sh './bin/run_tests -x java_sdk'
        }

        stage("Create git archive") {
            sh '''
                REPO=$(git remote show -n origin | grep Fetch | awk -F'[/.]' '{print $6}')
                VERSION=`git describe --dirty`
                git archive HEAD --format=zip -9 --output=$REPO-$VERSION.zip
                git archive HEAD --format=tgz -9 --output=$REPO-$VERSION.tgz
            '''
        }

        stage("Build the packages"){
            sh 'docker build . -f ci/sawtooth-build-debs -t sawtooth-build-debs:$ISOLATION_ID'
            sh 'docker run --rm -v $(pwd):/project/sawtooth-core sawtooth-build-debs:$ISOLATION_ID'
            sh 'docker build --no-cache . -f ci/sawtooth-test-debs -t sawtooth-test-debs:$ISOLATION_ID'
        }

        stage ("Build documentation") {
            sh 'docker build . -f ci/sawtooth-build-docs -t sawtooth-build-docs:$ISOLATION_ID'
            sh 'docker run --rm -v $(pwd):/project/sawtooth-core sawtooth-build-docs:$ISOLATION_ID'
        }

        stage("Archive Build artifacts") {
            archiveArtifacts artifacts: '*.tgz, *.zip'
            archiveArtifacts artifacts: 'build/debs/*.deb'
            archiveArtifacts artifacts: 'docs/build/html/**, docs/build/latex/*.pdf'
        }
    }
}
