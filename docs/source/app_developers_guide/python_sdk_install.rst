************************
Importing the Python SDK
************************

.. note::
   The Sawtooth Python SDK requires Python version 3.5 or higher

The Python SDK is installed automatically in the demo development environment,
as described by :doc:`installing_sawtooth`. This SDK is available through the
standard Python import system.

You can use the Python REPL to import the SDK into your Python environment,
then verify the import by viewing the SDK's docstring.

.. code-block:: console

    $ python3
    >>> import sawtooth_sdk
    >>> help(sawtooth_sdk)
    Help on package sawtooth_sdk:

    NAME
        sawtooth_sdk

    DESCRIPTION
        # Copyright 2016 Intel Corporation
        #
        # Licensed under the Apache License, Version 2.0 (the "License");
        # you may not use this file except in compliance with the License.
        # You may obtain a copy of the License at
        #
        #     http://www.apache.org/licenses/LICENSE-2.0
        #
        # Unless required by applicable law or agreed to in writing, software
        # distributed under the License is distributed on an "AS IS" BASIS,
        # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
        # See the License for the specific language governing permissions and
        # limitations under the License.
        # ------------------------------------------------------------------------------

    PACKAGE CONTENTS
        client (package)
        processor (package)
        protobuf (package)
        workload (package)

    DATA
        __all__ = ['client', 'processor']

    FILE
        /usr/lib/python3/dist-packages/sawtooth_sdk/__init__.py

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
