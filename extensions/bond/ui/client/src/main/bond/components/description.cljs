; Copyright 2016 Intel Corporation
;
; Licensed under the Apache License, Version 2.0 (the "License");
; you may not use this file except in compliance with the License.
; You may obtain a copy of the License at
;
;     http://www.apache.org/licenses/LICENSE-2.0
;
; Unless required by applicable law or agreed to in writing, software
; distributed under the License is distributed on an "AS IS" BASIS,
; WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
; See the License for the specific language governing permissions and
; limitations under the License.
; ------------------------------------------------------------------------------

(ns bond.components.description
  (:require [sablono.core :as html :refer-macros [html]]))

(defn landing-description []
  (html
    [:div

     [:div
      [:p "Welcome to Sawtooth’s proof-of-concept bond trading platform, built
          on the Sawtooth Lake distributed ledger."]
      [:p "Real-world bond trading, clearing, and settlement is significantly
          complex, but we have selected a core set of functionality that
          demonstrates how these platforms might be built on blockchain
          technology. Further investment would be required to move these
          concepts into production."]]

     [:div
      [:h4 "Capabilities:"]
      [:ul
       [:li "Create new participants with browser-managed WIF
            keys and browser-side transaction signing."]
       [:li "Create new organizations, both issuers and trading firms."]
       [:li "Create new bonds, US Treasury or Corporate, denominated in USD,
            with fixed or floating rates indexed on USD LIBOR."]
       [:li "Represent a trading firm as a Market Maker to issue quotes
            against bonds."]
       [:li "Represent a trading firm as a Trader to place orders against
            bonds, either market or limit."]
       [:li "View your firm’s holdings, settlements, and redemptions."]
       [:li "Quotes and orders automatically matched by the ledger itself."]
       [:li "Traders can settle matched orders, transfering assets between
            firms."]
       [:li "When coupon date or maturity date arrive, USD is automatically
            transfered from issuer to holder."]
       [:li "Bonds can have coupon frequencies of “Quarterly”, “Monthly”, and
            “Daily”. Select “Daily” to demonstrate coupon functionality
            during the test period."]]

       [:div
        [:p "We hope you enjoy exploring the capabilities of this proof-of-concept
            platform."]]

       [:div
        [:p "The Sawtooth Lake Team"]]]]))
