
*****************************
Application Developer's Guide
*****************************

This guide covers development of applications which run on top of the
Hyperledger Sawtooth platform, primarily through use of Sawtooth's provided
SDKs and REST API.  Topics covered include development of transaction families
and associated client programs. Transaction families codify business rules
used to modify state, while client programs typically submit transactions and
view state.

SDKs are provided in several languages: Go, Java, Javascript, and Python.

.. toctree::
   :maxdepth: 2

   app_developers_guide/environment_setup
   app_developers_guide/intro_to_sawtooth
   app_developers_guide/writing_clients
   app_developers_guide/address_and_namespace
   app_developers_guide/txn_family_tutorial
   app_developers_guide/testing
   app_developers_guide/javascript_sdk
   app_developers_guide/python_sdk
