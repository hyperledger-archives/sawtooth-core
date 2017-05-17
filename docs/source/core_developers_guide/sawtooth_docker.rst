
Docker
======

Overview
--------

Docker is a tool that allows for portable, containerized instances of
applications. It ensures repeatability and consistency across deployments
and platforms.

The included Dockerfiles are intended to make working with the Sawtooth
platform easy, whether you're a core developer or someone who's just interested
in trying it out.

Layout of the docker subdirectory
---------------------------------

The docker subdirectory is structured as follows:

.. code-block:: console

 ci/
  sawtooth-all
  sawtooth-tp_config
  sawtooth-tp_intkey_python
  ...
  sawtooth-validator
  
 docker/
  compose/
  sawtooth-dev-go
  sawtooth-dev-java
  sawtooth-dev-javascript
  sawtooth-dev-python
  ...
  sawtooth-int-rest_api
  sawtooth-int-tp_config
  ...


compose/
  Contains docker compose files for easily bringing up validator networks and
  connected transaction processors.

sawtooth-dev-\*
  Dockerfiles used for Hyperledger Sawtooth development in a given language. The
  default command for each image is to run the build commands needed to run the
  code in that language. These Dockerfiles are also used for local testing.

sawtooth-int-\*
  Dockerfiles used for testing Hyperledger Sawtooth in an installed environment.
  They copy in build artifacts from a local copy of the repository and install
  them.

sawtooth-\*
  Dockerfiles that build images with Hyperledger Sawtooth installed from the
  Hyperledger Sawtooth package repository. (http://repo.sawtooth.me) These
  Dockerfiles do not make any assumptions about the build or runtime
  environments.
