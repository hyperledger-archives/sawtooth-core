********************
Importing the Go SDK
********************

.. note::
   The Sawtooth Go SDK assumes that you have the latest version of Go,
   more information on installing and configuring can be found at `go
   <https://github.com/golang/go>`_.

Once you've got a working version of Sawtooth, there are a few additional
steps you'll need to take to get started developing for Sawtooth in Go.

1. Get Go SDK located at `Sawtooth Go SDK repository
   <https://github.com/hyperledger/sawtooth-sdk-go>`_.

.. code-block:: ini
    :caption: Run following command for downloading Go SDK

    $ go get github.com/hyperledger/sawtooth-sdk-go

2. Import the SDK into your Go files. You need to specify packages from SDK
   which are needed.

.. code-block:: ini
    :caption: Sample header for a Go file

    import (
        // to use signing package from SDK
        "github.com/hyperledger/sawtooth-sdk-go/signing"
    )

    // --snip--

3. Generate protobuf files for use, go to location
   ``$GOPATH/src/github.com/hyperledger/sawtooth-sdk-go`` and run ``go generate``

.. code-block:: ini
    :caption: Run following command for generating Go protobuf files

    $ go generate

4. Root location of generated protobuf is
   ``github.com/hyperledger/sawtooth-sdk-go/protobuf/``, notice that you may
   need ``"github.com/golang/protobuf/proto"`` for encoding / decoding.
   For example:

.. code-block:: go
    :caption: Sample header for a Go file using protobuf

    import (
        "github.com/golang/protobuf/proto"
        // For transaction protobuf structs
        "github.com/hyperledger/sawtooth-sdk-go/protobuf/transaction_pb2"
    )

    // --snip--

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
