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
        REGISTER_PARTICIPANT: "/mktplace.transactions.ParticipantUpdate/Register",
        REGISTER_WALLET: "/mktplace.transactions.AccountUpdate/Register",
        REGISTER_ASSET_TYPE: "/mktplace.transactions.AssetTypeUpdate/Register",
        REGISTER_ASSET: "/mktplace.transactions.AssetUpdate/Register",
        REGISTER_HOLDING: "/mktplace.transactions.HoldingUpdate/Register",
        REGISTER_SELL_OFFER: "/mktplace.transactions.SellOfferUpdate/Register",

        //unregister updates
        UNREGISTER_PARTICIPANT: "/mktplace.transactions.ParticipantUpdate/Unregister",
        UNREGISTER_WALLET: "/mktplace.transactions.AccountUpdate/Unregister",
        UNREGISTER_ASSET_TYPE: "/mktplace.transactions.AssetTypeUpdate/Unregister",
        UNREGISTER_ASSET: "/mktplace.transactions.AssetUpdate/Unregister",
        UNREGISTER_HOLDING: "/mktplace.transactions.HoldingUpdate/Unregister",
        UNREGISTER_SELL_OFFER: "/mktplace.transactions.SellOfferUpdate/Unregister",
        UNREGISTER_EXCHANGE: "/mktplace.transactions.ExchangeUpdate/Exchange",

        //exchange
        EXCHANGE: "/mktplace.transactions.ExchangeUpdate/Exchange"
    },

    DescriptionTypes : {
        PARTICIPANT : "MarketPlace Participant",
        ASSET_TYPE : "Currency asset type"
    },

    SignatureFieldNames :{
        TRANSACTION_SIGNATURE : "Signature",
        UPDATE_SIGNATURE:"__SIGNATURE__"
    },

    TRANSACTION_TYPE : "/MarketPlaceTransaction",
    MESSAGE_TYPE : "/mktplace.transaction.MarketPlace/Transaction",

};
