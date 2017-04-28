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
        body: batchBytes,
        headers: {'Content-Type': 'application/octet-stream'}
    }, (err, response) => {
        console.log(response)
    })

{% else %}

.. code-block:: python

    import urllib

    request = urllib.Request(
        'http://rest.api.domain/batches',
        batch_bytes,
        method='POST',
        headers={'Content-Type': 'application/octet-stream'})

    response = urllib.urlopen(request)

{% endif %}


And here is what it would look like if you saved the binary to a file, and then
sent it with *curl*:

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const fs = require('fs')

    const fileStream = fs.createWriteStream('intkey.batches')
    fileStream.write(batchBytes)
    fileStream.end()

{% else %}

.. code-block:: python

    output = open('batches.intkey', 'wb')
    output.write(batch_bytes)

{% endif %}

.. code-block:: bash

    % curl --request POST \
        --header "Content-Type: application/octet-stream" \
        --data-binary "intkey.batches" \
        "http://rest.api.domain/batches"
