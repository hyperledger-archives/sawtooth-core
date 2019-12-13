..
   Copyright 2017 Intel Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

.. _rest-api-cli-reference-label:

*****************
sawtooth-rest-api
*****************

The ``sawtooth-rest-api`` command starts the REST API and connects to
the validator.

The REST API is designed to run alongside a validator,
providing potential clients access to blockchain and state data
through common HTTP/JSON standards. It is a stateless process, and
does not store any part of the blockchain or blockchain state. Instead
it acts as a go between, translating HTTP requests into validator
requests, and sending back the results as JSON. As a result, running
the Sawtooth REST API requires that a validator already be running and
available over TCP.

Options for ``sawtooth-rest-api`` specify the bind address for the host and port
(by default, ``http://localhost:8008``) and the TCP address where the
validator is running (the default is ``tcp://localhost:4004``). An
optional timeout value configures how long the REST API will wait for
a response for the validator.

.. literalinclude:: output/sawtooth-rest-api_usage.out
   :language: console

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
