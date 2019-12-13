********************
Importing the Go SDK
********************

.. note::
   The Sawtooth Go SDK assumes that you have the latest version of Go.
   More information on installing and configuring go can be found in the
   `golang/go repository <https://github.com/golang/go>`__.

Once you've got a working version of Sawtooth, there are a few additional
steps you'll need to take to get started developing for Sawtooth in Go.

1. Get Go SDK located at `Sawtooth Go SDK repository
   <https://github.com/hyperledger/sawtooth-sdk-go>`__.

   Note that $GOPATH is a list of directories, the Go SDK is downloaded
   to the first directory entry present in it. We will assume that $GOPATH has
   been set to single directory for the rest of this document.

.. code-block:: console

    $ go get github.com/hyperledger/sawtooth-sdk-go

2. Import the SDK into your Go files. You need to specify which packages
   from the SDK are needed as in this example:

.. code-block:: go

    import (
        // to use signing package from SDK
        "github.com/hyperledger/sawtooth-sdk-go/signing"
    )

    // --snip--

3. Generate the protobuf files.

.. code-block:: console

    $ cd $GOPATH/src/github.com/hyperledger/sawtooth-sdk-go
    $ go generate

4. The Root location of the generated protobuf is
   ``github.com/hyperledger/sawtooth-sdk-go/protobuf/``.
   Notice that you may need ``"github.com/golang/protobuf/proto"`` for
   encoding / decoding.
   For example:

.. code-block:: go

    import (
        "github.com/golang/protobuf/proto"
        // For transaction protobuf structs
        "github.com/hyperledger/sawtooth-sdk-go/protobuf/transaction_pb2"
    )

    // --snip--

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
