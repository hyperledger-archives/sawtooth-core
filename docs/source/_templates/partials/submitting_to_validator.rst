Submitting Batches to the Validator
===================================

The prescribed way to submit Batches to the validator is via the REST API.
This is an independent process that runs alongside a validator, allowing clients
to communicate using HTTP/JSON standards. Simply send a *POST* request to the
*/batches* endpoint, with a *"Content-Type"* header of
*"application/octet-stream"*, and the *body* as a serialized *BatchList*.

There are a many ways to make an HTTP request, and hopefully the submission
process is fairly straightforward from here, but as an example, this is what it
might look if you sent the request from the same {{ language }} process that
prepared the BatchList:

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const request = require('request')

    request.post({
        url: 'http://rest.api.domain/batches',
        body: batchListBytes,
        headers: {'Content-Type': 'application/octet-stream'}
    }, (err, response) => {
        if (err) return console.log(err)
        console.log(response.body)
    })

{% elif language == 'Go' %}

.. code-block:: go

    import (
        "bytes"
        "net/http"
    )

    // Check if err is nil before continuing
    response, err := http.Post(
        "http://rest.api.domain/batches",
        "application/octet-stream",
        bytes.NewBuffer(batchListBytes)
    )

{% elif language == 'Rust' %}

.. code-block:: rust

    // When using an external crate don't forget to add it to your dependencies
    // in the Cargo.toml file, just like with the sdk itself
    extern crate reqwest;

    let client = reqwest::Client::new();
    let res = client
        .post("http://localhost:8008/batches")
        .header("Content-Type", "application/octet-stream")
        .body(
            batch_list_bytes,
        )
        .send()

{% else %}

.. code-block:: python

    import urllib.request
    from urllib.error import HTTPError

    try:
        request = urllib.request.Request(
            'http://rest.api.domain/batches',
            batch_list_bytes,
            method='POST',
            headers={'Content-Type': 'application/octet-stream'})
        response = urllib.request.urlopen(request)

    except HTTPError as e:
        response = e.file

{% endif %}


And here is what it would look like if you saved the binary to a file, and then
sent it from the command line with ``curl``:

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const fs = require('fs')

    const fileStream = fs.createWriteStream('intkey.batches')
    fileStream.write(batchListBytes)
    fileStream.end()

{% elif language == 'Go' %}

.. code-block:: go

    import (
        "io/ioutil"
    )

    // Check if err is nil before continuing
    err = ioutil.WriteFile("intkey.batches", batchListBytes, 0644)

{% elif language == 'Rust' %}

.. code-block:: rust

    use std::fs::File;
    use std::io::Write;

    let mut file = File::create("intkey.batches").expect("Error creating file");
    file.write_all(&batch_list_bytes)
        .expect("Error writing bytes");

{% else %}

.. code-block:: python

    output = open('intkey.batches', 'wb')
    output.write(batch_list_bytes)

{% endif %}

.. code-block:: bash

    % curl --request POST \
        --header "Content-Type: application/octet-stream" \
        --data-binary @intkey.batches \
        "http://rest.api.domain/batches"

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
