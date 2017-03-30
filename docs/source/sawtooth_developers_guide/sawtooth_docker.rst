
Docker
======

Overview
--------

Docker is a tool that allows for portable, containerized instances of
applications. It ensures repeatability and consistency across deployments
and platforms.

The included Dockerfiles are intended to make working with the Sawtooth Lake
platform easy, whether you're a core developer or someone who's just interested
in trying it out.

Layout of the docker subdirectory
---------------------------------

The docker subdirectory is structured as follows:

.. code-block:: console

 docker/
  compose/
  sawtooth-all
  sawtooth-build-java
  sawtooth-build-javascript
  ...
  sawtooth-dev-base
  sawtooth-dev-rest_api
  ...
  sawtooth-tp_config
  sawtooth-tp_intkey_python
  ...
  sawtooth-validator


compose/
  Contains docker compose files for easily bringing up validator networks and
  connected transaction processors.

sawtooth-build-\*
  Dockerfiles used to build the Sawtooth Lake source code without polluting the
  host environment. The containers should be run with the source code mounted
  inside the container.

  These Dockerfiles are built and run as part of the `build_all` command.
 
sawtooth-dev-\*
  Dockerfiles used for testing and development. 

  These Dockerfiles are built as part of the `build_all` command and run as part
  of the `run_tests` command.
 
sawtooth-\*
  Dockerfiles that build images with Sawtooth Lake installed from the Sawtooth
  Lake package repository (http://repo.sawtooth.me). These Dockerfiles
  do not make any assumptions about the build or runtime environments.
