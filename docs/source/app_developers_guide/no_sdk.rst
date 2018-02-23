**************************
Development Without an SDK
**************************

*Hyperledger Sawtooth* provides SDKs in a variety of languages to abstract away
a great deal of complexity and simplify developing applications for the
platform. The recommended way to work with Sawtooth is through one of these
SDKs wherever possible. However, if there is no SDK for your language of
choice, the SDK is missing some functionality, or you just want a deeper
understanding of what is going on underneath the hood, this guide will cover
developing for Sawtooth *without* the help of an SDK.

.. note::

   In addition to an overview of the underlying concepts, each guide includes
   copious code examples in *Python 3*. This is intended simply as a concrete
   demonstration in a common readable language. The material covered should
   apply to almost any language, and actual Python development should typically
   happen with the :doc:`Python SDK <python_sdk>`.

.. toctree::
   :maxdepth: 2

   ../_autogen/txn_submit_tutorial

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
