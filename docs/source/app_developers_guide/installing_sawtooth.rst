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

Sawtooth validators can be run from prebuilt
`Docker <https://www.docker.com/>`_ containers, installed natively using
`Ubuntu 16.04 <https://www.ubuntu.com/>`_ or launched in AWS from the
`AWS Marketplace <https://aws.amazon.com/marketplace/pp/B075TKQCC2>`_. To get
started, choose the platform appropriate to your use case and follow one of
the installation and usage guides below.

.. toctree::
	:maxdepth: 2

	docker.rst
	ubuntu.rst
	aws.rst

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
