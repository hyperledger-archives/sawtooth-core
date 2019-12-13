**************************************
Setting Up a Sawtooth Node for Testing
**************************************

Before you can start developing for the *Hyperledger Sawtooth* platform, you'll
need to set up a local Sawtooth node to test your application against. Once
the node is running, you will be able to submit new transactions and fetch the
resulting state and block data from the blockchain using HTTP and the Sawtooth
:doc:`REST API <../architecture/rest_api>`. The methods explained in this
section apply to the example transaction processors, *IntegerKey* and *XO*, as
well as any transaction processors you might write yourself.

.. note::

   To set up a multiple-node test environment, see
   :doc:`creating_sawtooth_network`.

You can install and run a single-node Sawtooth application development
environment using prebuilt `Docker <https://www.docker.com/>`_ containers,
a `Kubernetes <https://kubernetes.io>`_ cluster inside a virtual machine on
your computer, or a native `Ubuntu <https://www.ubuntu.com/>`_ installation.

To get started, choose the guide for the platform of your choice.

.. toctree::
	:maxdepth: 1

	docker.rst
	kubernetes.rst
	ubuntu.rst

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
