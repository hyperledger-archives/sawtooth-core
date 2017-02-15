#!groovy

// Copyright (c) 2017 Intel Corporation
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

node ('master') {
    // Create a unique workspace so Jenkins doesn't reuse an existing one
    ws("workspace/${env.BUILD_TAG}_0-7") {
        stage("Clone repo") {
            checkout scm
        }

        stage("Verify scripts") {
            readTrusted 'bin/build_all'
            readTrusted 'bin/build_debs'
            readTrusted 'bin/package_validator'
            readTrusted 'bin/run_lint'
            readTrusted 'bin/run_tests'
            readTrusted 'core/setup.py'
            readTrusted 'extensions/arcade/setup.py'
            readTrusted 'extensions/bond/setup.py'
            readTrusted 'extensions/mktplace/setup.py'
            readTrusted 'signing/setup.py'
            readTrusted 'validator/setup.py'
        }

        stage("Build docker build slave") {
            docker.build('sawtooth-build:$BUILD_TAG', \
            '-f docker/sawtooth-build-ubuntu-xenial .')
        }

        stage("Run Lint"){
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh './bin/build_all'
                    sh './bin/run_lint'
                }
            }
        }

        stage("Run Tests"){
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh './bin/build_all'
                    sh 'ENABLE_INTEGRATION_TESTS=1 ./bin/run_tests'
                    sh './bin/build_all'
                }
            }
        }

        stage("Build the packages"){
            docker.withServer('tcp://0.0.0.0:4243'){
                docker.image('sawtooth-build:$BUILD_TAG').inside {
                    sh 'VERSION=AUTO_STRICT ./bin/build_debs'
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
            archiveArtifacts artifacts: 'core/deb_dist/*.deb, \
                                        signing/deb_dist/*.deb, \
                                        *.deb, \
                                        extensions/arcade/deb_dist/*.deb, \
                                        extensions/bond/deb_dist/*.deb, \
                                        extensions/mktplace/deb_dist/*.deb'
            archiveArtifacts artifacts: 'docs/build/html/**, \
                                        docs/build/latex/*.pdf'
        }
    }
}
