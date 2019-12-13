Encoding Your Payload
=====================

Transaction payloads are composed of binary-encoded data that is opaque to the
validator. The logic for encoding and decoding them rests entirely within the
particular Transaction Processor itself. As a result, there are many possible
formats, and you will have to look to the definition of the Transaction
Processor itself for that information. As an example, the *IntegerKey*
Transaction Processor uses a payload of three key/value pairs encoded as
`CBOR <https://en.wikipedia.org/wiki/CBOR>`_. Creating one might look like this:

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const cbor = require('cbor')

    const payload = {
        Verb: 'set',
        Name: 'foo',
        Value: 42
    }

    const payloadBytes = cbor.encode(payload)

{% elif language == 'Go' %}

.. code-block:: go

    import (
        cbor "github.com/brianolson/cbor_go"
    )

    payloadData := make(map[string]interface{})
    payloadData["Verb"] = "set"
    payloadData["Name"] = "foo"
    payloadData["Value"] = 42

    // check if err is nil before continuing
    payloadBytes, err := cbor.Dumps(payloadData)

{% elif language == 'Rust' %}

.. code-block:: rust

    extern crate serde;
    extern crate serde_cbor;

    use serde::{Serialize, Deserialize};

    // Using serde to create a serializable struct
    #[derive(Debug, Serialize, Deserialize)]
    #[serde(rename_all = "PascalCase")]
    struct Payload {
        verb: String,
        name: String,
        value: u32,
    }

    // --snip--
    let payload = Payload{  verb : String::from("set"),
                            name : String::from("foo"),
                            value : 42 };

    let payload_bytes = serde_cbor::to_vec(&payload).expect("upsi");

{% else %}

.. code-block:: python

    import cbor

    payload = {
        'Verb': 'set',
        'Name': 'foo',
        'Value': 42}

    payload_bytes = cbor.dumps(payload)

{% endif %}

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
