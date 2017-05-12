
.. _environment_setup:

*****************
Environment Setup
*****************

This section walks through the process of setting up Hyperledger Sawtooth for
the purposes of application development.  After this setup, you will be ready
to perform application development tasks, such as implementing business logic
with transaction families and writing clients which use Sawtooth's REST API.

There are two options presented here for installing and running Sawtooth:

  - :ref:`env-docker-compose`
  - :ref:`env-ubuntu`

.. _env-docker-compose:

Installing Sawtooth Using Docker Compose 
========================================

Prerequisites
-------------

The following tools are required:

* `Docker Engine <https://docs.docker.com/engine/installation/>`_ (17.03.0-ce
  or later)
* `Docker Compose <https://docs.docker.com/compose/install/>`_ (Linux only)


Step One: Clone Repository
--------------------------

You'll need to have git installed in order to clone the Sawtooth Lake source
code repository. You can find up-to-date installation instructions here:

* `Git install instructions <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`_

.. note:: 

  When checking out Sawtooth Lake on Windows for use with vagrant, you should
  take steps to ensure that Windows-style CRLF line endings are not added to
  the code. The bash scripts used by your vagrant VM will not run correctly 
  with CRLF line endings. Git uses a configuration setting, *core.autocrlf*,
  to control whether or not LF-style line endings are automatically converted
  to CRLF-style line endings. `This setting should be set in such a way that 
  CRLFs are not introduced into your repository 
  <https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration>`_.

Open up a terminal and run the following:

.. code-block:: console

   % cd $HOME
   % mkdir project
   % cd project
   % git clone https://github.com/hyperledger/sawtooth-core.git

.. note::

  On a Windows environment, the suggested version of the last command
  above is:

  .. code-block:: console

      C:\> git clone https://github.com/hyperledger/sawtooth-core.git
      --config core.autocrlf=false


Environment Startup
-------------------

To start up the environment, run:

.. code-block:: console

  % cd sawtooth-core
  % docker-compose -f docker/compose/sawtooth-demo.yaml up

Downloading the docker images that comprise the Sawtooth Lake demo
environment can take serveral minutes. Once you see the containers
registering and creating intial blocks you can move on to the next step.

.. code-block:: console

  Attaching to compose_validator_1, compose_tp_xo_python_1, compose_client_1, compose_tp_intkey_python_1, compose_tp_config_1, compose_rest_api_1
  validator_1         | writing file: /etc/sawtooth/keys/validator.priv
  validator_1         | writing file: /etc/sawtooth/keys/validator.pub
  validator_1         | Generating /var/lib/sawtooth/genesis.batch
  tp_xo_python_1      | [19:03:47 DEBUG   selector_events] Using selector: ZMQSelector
  validator_1         | [19:03:47.537 INFO     path] Skipping path loading from non-existent config file: /etc/sawtooth/path.toml
  tp_xo_python_1      | [19:03:47 INFO    core] register attempt: OK
  validator_1         | [19:03:47.538 INFO     cli] config [path]: config_dir = "/etc/sawtooth"
  tp_intkey_python_1  | [19:03:47 DEBUG   selector_events] Using selector: ZMQSelector
  validator_1         | [19:03:47.538 INFO     cli] config [path]: key_dir = "/etc/sawtooth/keys"
  tp_intkey_python_1  | [19:03:47 INFO    core] register attempt: OK

Open a new terminal so we can connect to the client container:

.. code-block:: console

  % docker exec -it compose_client_1 bash

Your environment is ready for experimenting with Sawtooth. However, any work
done in this environment will be lost once the container exits. The demo
compose file provided is useful as a starting point for the creation of your
own Docker-based development environment. In order to use it for app
development, you need to take additional steps, such as mounting a host
directory into the container. See `Docker's documentation
<https://docs.docker.com/>`_ for details.


Resetting The Environment
-------------------------

If the environment needs to be reset for any reason, it can be returned to
the default state by logging out of the client container, then pressing
CTRL-c from the window where you originally ran docker-compose. Once the
containers have all shut down run 'docker-compose -f sawtooth-demo.yaml down'.

.. code-block:: console

  validator_1         | [00:27:56.753 DEBUG    interconnect] message round trip: TP_PROCESS_RESPONSE 0.03986167907714844
  validator_1         | [00:27:56.756 INFO     chain] on_block_validated: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  validator_1         | [00:27:56.761 INFO     chain] Chain head updated to: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  validator_1         | [00:27:56.762 INFO     publisher] Now building on top of block: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  validator_1         | [00:27:56.763 INFO     chain] Finished block validation of: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  Gracefully stopping... (press Ctrl+C again to force)
  Stopping compose_tp_xo_python_1 ... done
  Stopping compose_tp_config_1 ... done
  Stopping compose_client_1 ... done
  Stopping compose_rest_api_1 ... done
  Stopping compose_tp_intkey_python_1 ... done
  Stopping compose_validator_1 ... done

  % docker-compose -f docker/compose/sawtooth-demo.yaml down

Next Steps
----------

Continue on to :doc:`intro_to_sawtooth`

.. _env-ubuntu:

Installing Sawtooth on Ubuntu Linux
===================================

You can install Sawtooth directly on your Ubuntu Linux machine, using the
following steps:

Prerequisites
-------------

Ubuntu 16.04 or later

Installation
------------

Run the following commands from a terminal window, as root or with `sudo`:

.. code-block:: console

  $ echo "deb http://repo.sawtooth.me/ubuntu/0.8/stable xenial universe" >> /etc/apt/sources.list
  $ apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 6B58B1AC10FB5F63
  $ apt-get update && apt-get install -y sawtooth

Next Steps
----------

Continue on to :doc:`intro_to_sawtooth`
