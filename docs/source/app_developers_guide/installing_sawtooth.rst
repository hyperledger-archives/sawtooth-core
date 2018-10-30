*********************************************************
Setting Up a Sawtooth Application Development Environment
*********************************************************

Before you can start developing for the *Hyperledger Sawtooth* platform, you'll
need to set up and run a local validator to test your application against. Once
running, you will be able to submit new transactions and fetch the resulting
state and block data from the blockchain using HTTP and the Sawtooth
:doc:`REST API <../architecture/rest_api>`. The methods detailed here will apply
to the included example transaction families, *IntegerKey* and *XO*, as well
as any transaction families you might write yourself.

You can install and run a simple, single-node Sawtooth application development
environment on one of the following platforms:

- Docker: Run Sawtooth from prebuilt `Docker <https://www.docker.com/>`_
  containers.
- Ubuntu: Install Sawtooth natively using
  `Ubuntu 16.04 <https://www.ubuntu.com/>`_.
- Amazon Web Services (AWS): Launch Sawtooth in AWS from the
  `AWS Marketplace <https://aws.amazon.com/marketplace/pp/B075TKQCC2>`_.
- Kubernetes: Run Sawtooth in a single-node
  `Kubernetes <https://kubernetes.io>`_ cluster inside a virtual machine
  on your computer.

To get started, choose the guide for the platform of your choice.

.. note:

   The guides in this chapter set up an environment with one Sawtooth validator
   node. For a multiple-node environment, see :doc:`creating_sawtooth_network`.

.. toctree::
	:maxdepth: 1

	docker.rst
	ubuntu.rst
	aws.rst
	kubernetes.rst

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
