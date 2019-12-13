************************
Importing the Rust SDK
************************

.. note::
   The Sawtooth Rust SDK assumes that you have the latest version of Rust and
   its package manager Cargo, which can be installed with `rustup
   <https://rustup.rs/>`_.

Once you've got a working version of Sawtooth, there are a few additional
steps you'll need to take to get started developing for Sawtooth in Rust.

1. Add Sawtooth to your ``Cargo.toml`` file. Add sawtooth-sdk with the
   appropriate version to the dependencies section.  The Rust SDK is located in
   the Sawtooth SDK Rust repository
   `<http://github.com/hyperledger/sawtooth-sdk-rust>`_.

.. code-block:: ini
    :caption: Sample ``Cargo.toml`` for a Sawtooth Rust project

    [package]
    name = "package_name"
    version = "0.1.0"
    authors = ["..."]

    [dependencies]
    sawtooth-sdk = "0.2"
    // --snip--

2. Import the SDK into your Rust files. At the top of your files, specify
   ``extern crate sawtooth_sdk;`` and then ``use`` the packages you need from
   the Sawtooth SDK. For example:

.. code-block:: rust
    :caption: Sample header for a Rust file

    extern crate sawtooth_sdk;

    use sawtooth_sdk::processor::TransactionProcessor;

    // --snip--

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
