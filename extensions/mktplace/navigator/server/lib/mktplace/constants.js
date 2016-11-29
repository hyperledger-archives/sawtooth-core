/**
 * Copyright 2016 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */
"use strict";
module.exports = {
    UpdateTypes : {
        //register updates
        REGISTER_PARTICIPANT: "RegisterParticipant",
        REGISTER_ACCOUNT: "RegisterAccount",
        REGISTER_ASSET_TYPE: "RegisterAssetType",
        REGISTER_ASSET: "RegisterAsset",
        REGISTER_HOLDING: "RegisterHolding",
        REGISTER_SELL_OFFER: "RegisterSellOffer",

        //unregister updates
        UNREGISTER_PARTICIPANT: "UnregisterParticipant",
        UNREGISTER_ACCOUNT: "UnregisterAccount",
        UNREGISTER_ASSET_TYPE: "UnregisterAssetType",
        UNREGISTER_ASSET: "UnregisterAsset",
        UNREGISTER_HOLDING: "UnregisterHolding",
        UNREGISTER_SELL_OFFER: "UnregisterSellOffer",

        //exchange
        EXCHANGE: "Exchange"
    },

    TRANSACTION_TYPE : "/MarketPlaceTransaction",
    MESSAGE_TYPE : "/mktplace.transaction.MarketPlace/Transaction",

};
