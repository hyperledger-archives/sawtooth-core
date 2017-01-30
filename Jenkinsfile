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

node {
    // Create a unique workspace so Jenkins doesn't reuse an existing one
    ws("workspace/${env.BUILD_TAG}_0-8") {

        stage("Clone Repo") {
            checkout scm
        }
        stage("Verify Scripts") {
            readTrusted 'bin/build_all'
            readTrusted 'bin/run_tests'
            readTrusted 'core/setup.py'
            readTrusted 'extensions/arcade/setup.py'
            readTrusted 'signing/setup.py'
            readTrusted 'validator/setup.py'
        }

        // Use a docker container to build and protogen, so that the Jenkins
        // environment doesn't need all the dependencies.
        stage("Build Test Dependencies") {
            docker.build('sawtooth-build:$BUILD_TAG', '-f core/sawtooth/cli/data/sawtooth-build-ubuntu-xenial .')
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh './bin/build_all'
                }
            }
        }

        // Run the tests
        stage("Run 0-8 Tests"){
            // Required docker containers are built by the tests
            sh './bin/run_tests -p $(printf $BUILD_TAG | sha256sum | cut -c1-64)'
        }

        stage("Remove Docker Images") {
            sh 'docker rmi sawtooth-build:$BUILD_TAG'
        }
    }

    // Create a second unique workspace for 0-7 to avoid permission errors
    // built files and __pycache__ files.
    ws("workspace/${env.BUILD_TAG}_0-7") {
        stage("Clone repo") {
            checkout scm
        }

        stage("Verify scripts") {
            readTrusted 'bin/build_all'
            readTrusted 'bin/build_debs'
            readTrusted 'bin/package_validator'
            readTrusted 'bin/run_tests_0-7'
            readTrusted 'core/setup.py'
            readTrusted 'extensions/arcade/setup.py'
            readTrusted 'signing/setup.py'
            readTrusted 'validator/setup.py'
        }

        stage("Build docker build slave") {
            docker.build('sawtooth-build:$BUILD_TAG', '-f core/sawtooth/cli/data/sawtooth-build-ubuntu-xenial .')
        }

        stage("Run Tests"){
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh './bin/build_all'
                    sh './bin/run_tests_0-7'
                    sh './bin/build_all'
                }
            }
        }

        stage("Build the packages"){
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh './bin/build_debs'
                    stash name: 'debs', includes: 'core/deb_dist/*.deb,signing/deb_dist/*.deb,*.deb'
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
            archiveArtifacts artifacts: 'core/deb_dist/*.deb, signing/deb_dist/*.deb, *.deb'
            archiveArtifacts artifacts: 'docs/build/html/**, docs/build/latex/*.pdf'
        }
    }
}
