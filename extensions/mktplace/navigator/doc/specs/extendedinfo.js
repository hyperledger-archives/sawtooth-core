{
    "$schema" : "http://json-schema.org/schema#",

    "title" : "Ledger Explorer Extended Information",
    "id" : "http://tradenet.org/ledgerinfo#",

    "definitions" :
    {
        "ExtendedInformation" :
        {
            "id" : "#ExtendedInformation",
            "description" : "A record containing information about an asset, asset type, or participant",
            "type" : "object",
            "properties" :
            {
                "url" :
                {
                    "description" : "The URL for a page describing the object",
                    "type" : "string",
                    "format" : "URL",
                    "required" : false
                },

                "icon-url" :
                {
                    "description" : "The URL for a 64x64 icon to use for a symbolic representation of the object",
                    "type" : "string",
                    "format" : "URL",
                    "required" : false
                },

                "name" :
                {
                    "description" : "human readable name for the object",
                    "type" : "string",
                    "required" : false
                },

                "institution" :
                {
                    "description" : "human readable name for the organization responsible for the object",
                    "type" : "string",
                    "required" : false
                },

                "description" :
                {
                    "description" : "short paragraph describing the object",
                    "type" : "string",
                    "required" : false
                },

                "signature" :
                {
                    "description" : "ECDSA signature for the body of the transaction",
                    "type" : "string",
                    "required" : true
                },

            }
        }
    }
}
