****************************
Using Sawtooth with PoET-SGX
****************************

.. note::

   PoET-SGX is currently not compatible with Sawtooth 1.1. Users looking to
   leverage PoET-SGX should remain on Sawtooth 1.0. PoET-SGX is being upgraded
   to be made compatible with 1.1 and will be released before the end of 2018.

This procedure describes how to install, configure, and run Hyperledger Sawtooth
with PoET simulator consensus on a system with |Intel (R)| Software Guard
Extensions (SGX).

.. |Intel (R)| unicode:: Intel U+00AE .. registered copyright symbol

These instructions have been tested on Ubuntu 16.04 only.

Prerequisites
=============

.. _bios-update:

BIOS Update
-----------

.. Important::

    You may need to update your BIOS with a security fix before running
    Hyperledger Sawtooth with PoET. Affected versions and instructions for
    updating can be found on
    `Intel's website <https://security-center.intel.com/advisory.aspx?intelid=INTEL-SA-00076&languageid=en-fr>`_.
    If you're running an affected version, you must update the BIOS
    to ensure that these installation instructions work correctly.

You can verify the BIOS version after the machine has booted by running:

.. code-block:: console

    $ sudo lshw| grep -A5 *-firmware
         *-firmware
              description: BIOS
              vendor: Intel Corp.
              physical id: 0
              version: BNKBL357.86A.0050.2017.0816.2002
              date: 08/16/2017

.. _install-sgx:

Install SGX and PSW
===================

Install the prerequisites for SGX and the Intel SGX Platform Software (PSW).

.. code-block:: console

  $ sudo apt-get update &&
    sudo apt-get install -y \
        alien \
        autoconf \
        automake \
        build-essential \
        cmake \
        libcurl4-openssl-dev \
        libprotobuf-dev \
        libssl-dev \
        libtool \
        libxml2-dev \
        ocaml \
        pkg-config \
        protobuf-compiler \
        python \
        unzip \
        uuid-dev \
        wget

Download and install the SGX driver:

.. code-block:: console

    $ mkdir ~/sgx && cd ~/sgx
    $ wget https://download.01.org/intel-sgx/linux-2.0/sgx_linux_x64_driver_eb61a95.bin
    $ chmod +x sgx_linux_x64_driver_eb61a95.bin
    $ sudo ./sgx_linux_x64_driver_eb61a95.bin

Download and install the Intel Capability Licensing Client. This is presently
available only as an .rpm, so you must convert it to a .deb package with
alien:

.. code-block:: console

    $ wget http://registrationcenter-download.intel.com/akdlm/irc_nas/11414/iclsClient-1.45.449.12-1.x86_64.rpm
    $ sudo alien --scripts iclsClient-1.45.449.12-1.x86_64.rpm
    $ sudo dpkg -i iclsclient_1.45.449.12-2_amd64.deb

Download and install the Dynamic Application Loader Host Interface (JHI):

.. code-block:: console

    $ wget https://github.com/01org/dynamic-application-loader-host-interface/archive/master.zip -O jhi-master.zip
    $ unzip jhi-master.zip && cd dynamic-application-loader-host-interface-master
    $ cmake .
    $ make
    $ sudo make install
    $ sudo systemctl enable jhi

Download and install the Intel SGX Platform Software (PSW):

.. code-block:: console

    $ cd ~/sgx
    $ wget https://download.01.org/intel-sgx/linux-2.0/sgx_linux_ubuntu16.04.1_x64_psw_2.0.100.40950.bin
    $ chmod +x sgx_linux_ubuntu16.04.1_x64_psw_2.0.100.40950.bin
    $ sudo ./sgx_linux_ubuntu16.04.1_x64_psw_2.0.100.40950.bin

Check to make sure the kernel module is loaded:

.. code-block:: console

    $ lsmod | grep sgx
    isgx                   36864  2

If the output does not show the isgx module, make sure that
SGX is set to "Enabled" in the BIOS.

If you're still having trouble, the SGX software may need to be reinstalled:

.. code-block:: console

    $ sudo /opt/intel/sgxpsw/uninstall.sh
    $ cd ~/sgx
    $ sudo ./sgx_linux_x64_driver_eb61a95.bin
    $ sudo ./sgx_linux_ubuntu16.04.1_x64_psw_2.0.100.40950.bin

After ensuring that the SGX kernel module is loaded, go to the next section
to install and configure Sawtooth.


Configuring Sawtooth to Use PoET-SGX
====================================

This section describes the Sawtooth steps to configure PoET-SGX consensus.

Install Sawtooth
----------------

.. code-block:: console

    $ sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8AA7AF1F1091A5FD
    $ sudo add-apt-repository 'deb [arch=amd64] http://repo.sawtooth.me/ubuntu/bumper/stable xenial universe'
    $ sudo apt-get update
    $ sudo apt-get install -y \
      sawtooth \
      python3-sawtooth-poet-engine \
      python3-sawtooth-poet-sgx

Certificate File
----------------

The configuration process requires an SGX certificate file in PEM format
(.pem), which you will need before continuing.

Instructions for creating your own service provider certificate can be found
`here <https://software.intel.com/en-us/articles/how-to-create-self-signed-certificates-for-use-with-intel-sgx-remote-attestation-using>`_.

After your certificate is created, you'll need to register it with the
attestation service.
`Click here <https://software.intel.com/formfill/sgx-onboarding>`_ for the
registration form.

Configure the Validator for PoET-SGX
------------------------------------

After installing Sawtooth, add config settings so PoET-SGX will work properly.


Create the file ``/etc/sawtooth/poet_enclave_sgx.toml``
with your favorite editor (such as vi):

.. code-block:: console

    $ sudo vi /etc/sawtooth/poet_enclave_sgx.toml

Add the following lines, replacing [example] with the spid value provided by
Intel:

.. code-block:: ini

    # Service Provider ID. It is linked to the key pair used to authenticate with
    # the attestation service.

    spid = '[example]'

    # ias_url is the URL of the Intel Attestation Service (IAS) server.

    ias_url = 'https://test-as.sgx.trustedservices.intel.com:443'

    # spid_cert_file is the full path to the PEM-encoded certificate file that was
    # submitted to Intel in order to obtain a SPID

    spid_cert_file = '/etc/sawtooth/sgx-certificate.pem'

Next, install the .pem certificate file that you downloaded earlier.
Replace [example] in the path below with the path to the certificate file on
your local system:

.. code-block:: console

    $ sudo install -o root -g sawtooth -m 640 \
    /[example]/sgx-certificate.pem /etc/sawtooth/sgx-certificate.pem

Create validator keys:

.. code-block:: console

    $ sudo sawadm keygen

.. note::  If you're configuring multiple validators, the steps below are
    required for the first validator only.  For additional validators, you
    can skip the rest of this procedure. Continue with :ref:`val-config`.

Become the ``sawtooth`` user and change to ``/tmp``.
In the following commands, the prompt ``[sawtooth@system]`` shows the commands
that must be executed as the ``sawtooth`` user.

.. code-block:: console

    $ sudo -u sawtooth -s
    [sawtooth@system]$ cd /tmp

Create a genesis batch:

.. code-block:: console

    [sawtooth@system]$ sawset genesis --key /etc/sawtooth/keys/validator.priv -o config-genesis.batch

Create and submit a proposal:

.. code-block:: console

    [sawtooth@system]$ sawset proposal create -k /etc/sawtooth/keys/validator.priv \
    sawtooth.consensus.algorithm.name=PoET \
    sawtooth.consensus.algorithm.version=0.1 \
    sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/ias_rk_pub.pem)" \
    sawtooth.poet.valid_enclave_measurements=$(poet enclave --enclave-module sgx measurement) \
    sawtooth.poet.valid_enclave_basenames=$(poet enclave --enclave-module sgx basename) \
    sawtooth.poet.enclave_module_name=sawtooth_poet_sgx.poet_enclave_sgx.poet_enclave \
    -o config.batch

When the ``sawset proposal`` command runs, you should see several
lines of output showing that the SGX enclave has been initialized:

.. code-block:: console

    [12:03:58 WARNING poet_enclave] SGX PoET enclave initialized.
    [12:03:59 WARNING poet_enclave] SGX PoET enclave initialized.

.. note::

    There’s quite a bit going on in the previous ``sawset proposal`` command, so
    let’s take a closer look at what it accomplishes:

    ``sawtooth.consensus.algorithm.name=PoET``
      Changes the consensus algorithm to PoET.

    ``sawtooth.consensus.algorithm.version=0.1``
      Changes the version of the consensus algorithm to 0.1.

    ``sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/ias_rk_pub.pem)"``
      Adds the public key that the validator registry transaction processor uses
      to verify attestation reports.

    ``sawtooth.poet.valid_enclave_measurements=$(poet enclave --enclave-module sgx measurement)``
      Adds the enclave measurement for your enclave to the blockchain for the
      validator registry transaction processor to use to check signup information.

    ``sawtooth.poet.valid_enclave_basenames=$(poet enclave --enclave-module sgx basename)``
      Adds the enclave basename for your enclave to the blockchain for the
      validator registry transaction processor to use to check signup information.

    ``sawtooth.poet.enclave_module_name``
      Specifies the name of the Python module that implements the PoET enclave.
      In this case, ``sawtooth_poet_sgx.poet_enclave_sgx.poet_enclave`` is the
      SGX version of the enclave; it includes the Python code as well as the
      Python extension.

Create a poet-genesis batch:

.. code-block:: console

    [sawtooth@system]$ poet registration create -k /etc/sawtooth/keys/validator.priv \
      --enclave-module sgx -o poet_genesis.batch
    Writing key state for PoET public key: 0387a451...9932a998
    Generating poet_genesis.batch

Create a genesis block:

.. code-block:: console

    [sawtooth@system]$ sawadm genesis config-genesis.batch config.batch poet_genesis.batch

You’ll see some output indicating success:

.. code-block:: console

    Processing config-genesis.batch...
    Processing config.batch...
    Processing poet_genesis.batch...
    Generating /var/lib/sawtooth/genesis.batch

Genesis configuration is complete! Log out of the sawtooth account:

.. code-block:: console

    [sawtooth@system]$ exit
    $


.. _val-config:

Change the Validator Config File
--------------------------------

You must specify some networking information so that the validator advertises
itself properly and knows where to search for peers.
Create the file ``/etc/sawtooth/validator.toml``:

.. code-block:: console

    $ sudo vi /etc/sawtooth/validator.toml

Add the following content to the file:

.. code-block:: ini

    #
    # Hyperledger Sawtooth -- Validator Configuration
    #

    # This file should exist in the defined config directory and allows
    # validators to be configured without the need for command line options.

    # The following is a possible example.

    # Bind is used to set the network and component endpoints. It should be a list
    # of strings in the format "option:endpoint", where the options are currently
    # network and component.
    bind = [
      "network:tcp://eno1:8800",
      "component:tcp://127.0.0.1:4004",
      "consensus:tcp://127.0.0.1:5050"
    ]

    # The type of peering approach the validator should take. Choices are 'static'
    # which only attempts to peer with candidates provided with the peers option,
    # and 'dynamic' which will do topology buildouts. If 'dynamic' is provided,
    # any static peers will be processed first, prior to the topology buildout
    # starting.
    peering = "dynamic"

    # Advertised network endpoint URL.
    endpoint = "tcp://[external interface]:[port]"

    # Uri(s) to connect to in order to initially connect to the validator network,
    # in the format tcp://hostname:port. This is not needed in static peering mode
    # and defaults to None.
    seeds = ["tcp://[seed address 1]:[port]",
             "tcp://[seed address 2]:[port]"]

    # A list of peers to attempt to connect to in the format tcp://hostname:port.
    # It defaults to None.
    peers = []

    # The type of scheduler to use. The choices are 'serial' or 'parallel'.
    scheduler = 'serial'

    # A Curve ZMQ key pair are used to create a secured network based on side-band
    # sharing of a single network key pair to all participating nodes.
    # Note if the config file does not exist or these are not set, the network
    # will default to being insecure.
    #network_public_key = ''
    #network_private_key = ''

Next, locate the ``endpoint`` section in this file.
Replace the external interface and port values with either the
publicly addressable IP address and port or the NAT values for your validator.

.. code-block:: ini

    endpoint = "tcp://[external interface]:[port]"

Find the ``seeds`` section in the config file.
Replace the seed address and port values with either the
publicly addressable IP address and port or the NAT values for the other nodes
in your network.

.. code-block:: ini

    seeds = ["tcp://[seed address 1]:[port]",
             "tcp://[seed address 2]:[port]"]

If necessary, change the network bind interface in the ``bind`` section.

.. code-block:: ini

    bind = [
      "network:tcp://eno1:8800",
      "component:tcp://127.0.0.1:4004",
      "consensus:tcp://127.0.0.1:5050"
    ]

The default network bind interface is "eno1". If this device
doesn't exist on your machine, change the ``network`` definition to
specify the correct bind interface.

.. tip::

    Make sure that all values in this setting are valid for your network.
    If the bind interface doesn't exist,
    you may see a ZMQ error in the sawtooth-validator
    systemd logs when attempting to start the validator, as in this example\:

    .. code-block:: console

        Jun 02 14:50:37 ubuntu validator[15461]:   File "/usr/lib/python3.5/threading.py", line 862, in run
        ...
        Jun 02 14:50:37 ubuntu validator[15461]:   File "zmq/backend/cython/socket.pyx", line 487, in zmq.backend.cython.socket.Socket.bind (zmq/backend/cython/socket.c:5156)
        Jun 02 14:50:37 ubuntu validator[15461]:   File "zmq/backend/cython/checkrc.pxd", line 25, in zmq.backend.cython.checkrc._check_rc (zmq/backend/cython/socket.c:7535)
        Jun 02 14:50:37 ubuntu validator[15461]: zmq.error.ZMQError: No such device
        Jun 02 14:50:37 ubuntu systemd[1]: sawtooth-validator.service: Main process exited, code=exited, status=1/FAILURE
        Jun 02 14:50:37 ubuntu systemd[1]: sawtooth-validator.service: Unit entered failed state.
        Jun 02 14:50:37 ubuntu systemd[1]: sawtooth-validator.service: Failed with result 'exit-code'.

(Optional) Change the network keys to specify secured network communication
between nodes in the network. By default, the network is unsecured.

Locate the ``network_public_key`` and ``network_private_key`` settings.
These items specify the curve ZMQ key pair used to create a secured
network based on side-band sharing of a single network key pair to all
participating nodes.

Next, generate your network keys.

 * This example shows how to use Python to generate these keys:

   .. code-block:: python

       python
        ...
       >>> import zmq
       >>> (public, secret) = zmq.curve_keypair()
       >>> print public
       wFMwoOt>yFqI/ek.G[tfMMILHWw#vXB[Sv}>l>i)
       >>> print secret
       r&oJ5aQDj4+V]p2:Lz70Eu0x#m%IwzBdP(}&hWM*

 * Or you could use the following steps to compile and run ``curve_keygen``
   to generate the keys:

   .. code-block:: console

      $ sudo apt-get install g++ libzmq3-dev
        ...
      $ wget https://raw.githubusercontent.com/zeromq/libzmq/master/tools/curve_keygen.cpp
       ...
      $ g++ curve_keygen.cpp -o curve_keygen -lzmq

      $./curve_keygen
      == CURVE PUBLIC KEY ==
      -so<iWpS=5uINn*eV$=J)F%lEFd=@g:g@GqmL2C]
      == CURVE SECRET KEY ==
      G1.mNaJLnJxb6BWsY=P[K3D({+uww!T&LC3(Xq:B

Finally, replace the example values in the validator config file with your
unique network keys.

.. code-block:: ini

    network_public_key = '{nw-public-key}'
    network_private_key = '{nw-private-key}'

After saving your changes,
restrict permissions on ``validator.toml`` to protect the network private key.

.. code-block:: console

    $ sudo chown root:sawtooth /etc/sawtooth/validator.toml
    $ sudo chown 640 /etc/sawtooth/validator.toml

.. _rest-api-config:

Change the REST API Config File
-------------------------------

Create the REST API configuration file, ``/etc/sawtooth/rest_api.toml``
by copying the example file from ``/etc/sawtooth/rest_api.toml.example``.

.. code-block:: console

    $ sudo cp /etc/sawtooth/rest_api.toml.example /etc/sawtooth/rest_api.toml

Use ``sudo`` to edit this file.

.. code-block:: console

    $ sudo vi /etc/sawtooth/rest_api.toml

If necessary, change the ``bind`` setting to specify where the REST API
listens for incoming communication.
Be sure to remove the ``#`` comment character to activate this setting.

.. code-block:: console

    bind = ["127.0.0.1:8008"]

If necessary, change the ``connect`` setting, which specifies where the
REST API can find this node's validator on the network.
Be sure to remove the ``#`` comment character to activate this setting.

.. code-block:: console

    connect = "tcp://localhost:4004"

.. note::

   To learn how to put the REST API behind a proxy server,
   see :doc:`rest_auth_proxy`.


Start the Sawtooth Services
---------------------------

Use these commands to start the Sawtooth services:

.. code-block:: console

    $ sudo systemctl start sawtooth-rest-api.service
    $ sudo systemctl start sawtooth-poet-validator-registry-tp.service
    $ sudo systemctl start sawtooth-poet-engine.service
    $ sudo systemctl start sawtooth-validator.service
    $ sudo systemctl start sawtooth-settings-tp.service
    $ sudo systemctl start sawtooth-intkey-tp-python.service
    $ sudo systemctl start sawtooth-identity-tp.service

You can follow the logs by running:

.. code-block:: console

    $ sudo journalctl -f \
    -u sawtooth-validator \
    -u sawtooth-settings-tp \
    -u sawtooth-poet-validator-registry-tp \
    -u sawtooth-poet-engine \
    -u sawtooth-rest-api \
    -u sawtooth-intkey-tp-python \
    -u sawtooth-identity-tp

Additional logging output can be found in ``/var/log/sawtooth/``.
For more information, see :doc:`log_configuration`.

To verify that the services are running:

.. code-block:: console

    $ sudo systemctl status sawtooth-rest-api.service
    $ sudo systemctl status sawtooth-poet-validator-registry-tp.service
    $ sudo systemctl status sawtooth-poet-engine.service
    $ sudo systemctl status sawtooth-validator.service
    $ sudo systemctl status sawtooth-settings-tp.service
    $ sudo systemctl status sawtooth-intkey-tp-python.service
    $ sudo systemctl status sawtooth-identity-tp.service

Stop or Restart the Sawtooth Services
-------------------------------------

If you need to stop or restart the Sawtooth services for any reason, use the
following commands:

Stop Sawtooth services:

.. code-block:: console

    $ sudo systemctl stop sawtooth-rest-api.service
    $ sudo systemctl stop sawtooth-poet-validator-registry-tp.service
    $ sudo systemctl stop sawtooth-poet-engine.service
    $ sudo systemctl stop sawtooth-validator.service
    $ sudo systemctl stop sawtooth-settings-tp.service
    $ sudo systemctl stop sawtooth-intkey-tp-python.service
    $ sudo systemctl stop sawtooth-identity-tp.service

Restart Sawtooth services:

.. code-block:: console

    $ sudo systemctl restart sawtooth-rest-api.service
    $ sudo systemctl restart sawtooth-poet-validator-registry-tp.service
    $ sudo systemctl restart sawtooth-poet-engine.service
    $ sudo systemctl restart sawtooth-validator.service
    $ sudo systemctl restart sawtooth-settings-tp.service
    $ sudo systemctl restart sawtooth-intkey-tp-python.service
    $ sudo systemctl restart sawtooth-identity-tp.service

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
