#!groovy

node {
  stage("Clone repo") {
    checkout scm
  }

  stage("Verify scripts") {
    readTrusted 'bin/build_all'
    readTrusted 'bin/build_debs'
    readTrusted 'bin/run_tests'
  }

  stage("Build docker slave") {
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

  stage("Remove docker image") {
    sh 'docker rmi sawtooth-build:$BUILD_TAG'
  }

  stage("Archive Build artifacts") {
    archiveArtifacts artifacts: 'core/deb_dist/*.deb,signing/deb_dist/*.deb,*.deb'
  }
}
