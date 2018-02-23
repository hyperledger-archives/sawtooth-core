
*****************************
Application Developer's Guide
*****************************

This guide describes how to develop applications which run on top of the
Hyperledger Sawtooth :term:`core platform<Sawtooth core>`, primarily through
the use of Sawtooth's provided SDKs and :term:`REST API`.

Topics include developing a :term:`transaction family<Transaction family>` and
an associated client program. Transaction families codify business rules used
to modify state, while client programs typically submit transactions and view
state.

Sawtooth provides SDKs in several languages, including Python, Javascript, Go,
C++, Java, and Rust. This guide has tutorials for using the Go, Javascript, and
Python SDKs.

.. toctree::
   :maxdepth: 2

   app_developers_guide/overview
   app_developers_guide/sdk_table
   app_developers_guide/installing_sawtooth
   app_developers_guide/intro_xo_transaction_family
   app_developers_guide/go_sdk
   app_developers_guide/javascript_sdk
   app_developers_guide/python_sdk
   app_developers_guide/no_sdk
   app_developers_guide/address_and_namespace
   app_developers_guide/event_subscriptions

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
