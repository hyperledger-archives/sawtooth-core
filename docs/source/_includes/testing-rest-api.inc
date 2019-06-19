* Confirm that the REST API is reachable.

  .. code-block:: console

     $ curl http://localhost:8008/blocks

  .. note::

     The Sawtooth environment described this guide runs a local REST API on
     each node. For a node that is not running a local REST API,
     replace ``localhost:8008`` with the externally advertised IP address and
     port.

  You should see a JSON response that is similar to this example:

  .. code-block:: console

     {
       "data": [
         {
           "batches": [
             {
               "header": {
                 "signer_public_key": . . .

  If not, check the status of the REST API service and restart it, if necessary.

