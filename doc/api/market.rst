=================================================================
/market
=================================================================

.. http:get:: /market/{participant}

   Returns the object with the object name matching `participant`.

.. http:get:: /market/{participant}/{obj_name_path}

   Returns the object with the object name matching "/" + `obj_name_path`
    and a creator_id matching that of the object with name `participant`.

**Example request**:

.. sourcecode:: http

    GET /market/marketplace HTTP/1.1
    Host: localhost:8800
    User-Agent: curl/7.43.0
    Accept: */*


**Example response**:

.. sourcecode:: http

    HTTP/1.1 200 OK
    Date: Sat, 20 Feb 2016 00:39:17 GMT
    Content-Length: 194
    Content-Type: application/json

    {
      "address": "1Q3mt8e119nPSeMCeDPAhfZ943oqcLmGir",
      "description": "The ROOT participant for the marketplace",
      "identifier": "54cf2c447f4a1f1b",
      "name": "marketplace",
      "object-type": "Participant"
    }


**Example**:

.. sourcecode:: http

    GET /market/marketplace/asset-type/token

.. sourcecode:: javascript

    {
      "creator": "54cf2c447f4a1f1b",
      "description": "Canonical type for meaningless tokens that are very useful for bootstrapping",
      "identifier": "9f37f8dc69a82bb5",
      "name": "/asset-type/token",
      "object-type": "AssetType",
      "restricted": true
    }

.. note:: Note that the creator id 54cf2c447f4a1f1b of the /asset-type/token object matches the identifier of
    the marketplace in the example above.