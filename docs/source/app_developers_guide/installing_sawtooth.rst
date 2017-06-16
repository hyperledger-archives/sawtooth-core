*******************************
Installing and Running Sawtooth
*******************************

Before you can start developing for the *Hyperledger Sawtooth* platform, you'll
need to set up and run a local validator to test your application against. Once
running, you will be able to submit new transactions and fetch the resulting
state and block data from the blockchain using HTTP and the Sawtooth
:doc:`REST API <../architecture/rest_api>`. The methods detailed here will apply
both to the included example transaction families, *IntKey* and *Xo*, as well
as any transaction families you might write yourself.

Sawtooth validators can be run either from prebuilt
`Docker <https://www.docker.com/>`_ containers, or natively using
`Ubuntu 16.04 <https://www.ubuntu.com/>`_. To get started, choose the platform
appropriate to your use case and follow one of the the installation and usage
guides below.

.. toctree::
	:maxdepth: 2

	docker.rst
	ubuntu.rst
