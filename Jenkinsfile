#!groovy

node {
  stage("Clone repo") {
    checkout scm
  }

  stage("Verify scripts") {
    readTrusted 'bin/build_all'
    readTrusted 'bin/build_debs'
    readTrusted 'bin/package_validator'
    readTrusted 'bin/run_tests'
  }

  stage("Build docker build slave") {
    docker.build('sawtooth-build:$BUILD_TAG', '-f core/sawtooth/cli/data/sawtooth-build-ubuntu-xenial .')
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
