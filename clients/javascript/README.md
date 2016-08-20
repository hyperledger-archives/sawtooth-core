# Sawtooth Node JS Client

A library for interfacing with a Sawtooth Validator.


## Installing

To install, simply run:

```
> npm install <git repository>
```

## Usage

Start by requiring the package:

```
> var sawtooth = require('sawtooth-client');
```

### Connecting to a Validator

First, we can create a `ValidatorClient` to a given validator.

```
> var validator = new sawtooth.ValidatorClient('<validator_host>', 8800);
```

The validator client provides a series of opertions against the web API.
Each method returns a JavaScript Promise, which will return the queried
information.

#### Stores

Using a validator client instance, the following api calls are provided for
retrieving details about stores in the validator:

- *getStores()* returns the list of stores
- *getStore(storeName)* returns a list of object ids in the given store
- *getStoreObjects(storeName)* returns a list of objects in the given store
- *getStoreObject(storeName, key)* returns the value of the object in the
    given storeName with the given key

For example, we can get the list of stores from the validator client we
constructed above:

```
> validator.getStores().then((stores) => console.log(stores))
Promise { <pending> }
> [ '/IntegerKeyTransaction',
  '/EndpointRegistryTransaction',
  '/MarketPlaceTransaction' ]
```

These store names can be used with successive calls to the validator as is, or
shortened by dropping the leading `/`.

For example:

```
> validator.getStore('MarketPlaceTransaction').then(ids => console.log(ids))
Promise { <pending> }
> [ '8204e9f088c5102c',
  '5609937b1edb2a64',
  '94fa21fe21cfe8c9',
    ...
  '0bb2953ed12d0724',
  'c9510eafb98c2487' ]
```

#### Signing and Submitting Transactions

A transaction may be submitted to the validator via the method
`sendTransaction`. This method takes a transaction family name and a
transaction as either a JSON string, or a CBOR-encoded buffer.

CBOR is recommended as it handles float fields correctly.

For example, sending a MarketplaceTransaction:

```
var signedTxn = sawtooth.signUpdate(
    '/mktplace.transactions.MarketPlace/Transaction',
    {
        UpdateType "/mktplace.transactions.ParticipantUpdate/Register",
        Name: "My Paritipant",
        Description: "This belongs to me",
    },
    '<my signing key in WIF format>',
    {output: 'cbor'});

validator.sendTransaction('/mktplace.transactions.MarketPlace/Transaction',
                          signedTxn)
    .then(txnId => console.log(txnId));;
```

If any fields must be a float, the transaction can be signed using an
additional option of `ratios` with an array of field names.  For example:

```

var signedTxn = sawtooth.signUpdate(
    '/mktplace.transactions.MarketPlace/Transaction',
    {
        UpdateType: "/mktplace.transactions.SellOfferUpdate/Register",
        ...
        Ratio: 1
        ...
    },
    '<my signing key in WIF format>',
    {
        output: 'cbor',
        ratios: ['Ratio']
    });
```

The resulting CBOR will ensure that it will be decoded with `Ratio` equal to
`1.0` in environments that support floats (e.g. Python).

## Development

The package tests may be run using:

```
> npm test
```

Tests require Node 6.x, though the library does not.
