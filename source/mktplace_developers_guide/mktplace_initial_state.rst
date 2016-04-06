-----------------------------------------------------------------
MarketPlace Initial State
-----------------------------------------------------------------

The MarketPlace creates several asset types and assets that enable
markets to "bootstrap" participation. All bootstrap asset types and
assets are created by an initial participant with the name
"marketplace". 

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Asset Types
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Two asset types are created for bootstrapping:

    - /asset-type/participant -- This is an asset type for creating
      participants as an asset, the participant asset type is not
      restricted meaning that anyone can create a participant asset

    - /asset-type/token -- This is an asset type for creating the
      various token assets used for meta-operations of the market, the
      token asset type is restricted meaning that only the marketplace
      can create token assets

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Assets
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Currently only one asset is created for bootstrapping:

    - /asset/token -- a canonical asset for bootstrap tokens, the asset
      is not restricted (meaning that any participant can create a
      holding with a token in it), non-consumable (meaning that having a
      single token is equivalent to having an infinite number of tokens)

The token asset is particularly useful for creating "gift" offers that
take tokens as input and give some other asset as output. 
