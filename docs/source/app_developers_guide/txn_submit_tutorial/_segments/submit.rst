Submitting Batches to the Validator
===================================

The prescribed way to submit Batches to the validator is using the REST API. This is an independent process that runs alongside a validator, allowing clients to communicate using HTTP/JSON standards. Simply send a POST request to the */batches* endpoint, with a *"Content-Type"* header of *"application/octet-stream"*, and the body a serialized *BatchList*.

There are a many ways to make an HTTP request, and hopefully the submission process is fairly straightforward from here, but this is what it might look if you sent the request from the same process that prepared the BatchList: