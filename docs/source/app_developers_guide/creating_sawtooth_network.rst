********************************
Creating a Sawtooth Test Network
********************************

This section describes how to create a Sawtooth network for an application
development environment. Each node is similar to the single-node environment
described :doc:`earlier in this guide <installing_sawtooth>`, but the network
uses a consensus algorithm that is appropriate for a Sawtooth network (instead
of Devmode consensus). For more information, see :doc:`about_sawtooth_networks`.

.. note::

   For a single-node test environment, see :doc:`installing_sawtooth`.

Use the procedures in this section to create a Sawtooth test network using
prebuilt `Docker <https://www.docker.com/>`__ containers,
a `Kubernetes <https://kubernetes.io>`__ cluster inside a virtual machine on
your computer, or a native `Ubuntu <https://www.ubuntu.com/>`__ installation.

To get started, read :doc:`about_sawtooth_networks`, then choose the guide for
the platform of your choice.

.. toctree::
   :maxdepth: 2

   about_sawtooth_networks
   docker_test_network
   kubernetes_test_network
   ubuntu_test_network


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
