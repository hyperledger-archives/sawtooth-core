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
      [:p "Welcome to Intel’s proof-of-concept Bond Trading Platform, built on
          the Sawtooth Lake distributed ledger."]
      [:p "Real-world bond trading, clearing, and settlement is significantly
          complex, so we have attempted to select a core set of functionality
          that demonstrates how these platforms might be built on blockchain
          technology. Further investment would be required to move these
          concepts into production."]]

     [:div
      [:h4 "Components:"]
      [:ul
       [:li "Bond Trading Platform Transaction Family"]
       [:li "Bond Trading Platform Command Line Interface"]
       [:li "Bond Trading Platform User Interface"]]]

     [:div
      [:h4 "Capabilities:"]
      [:ul
       [:li "Ability to create new participants with browser-managed private
            keys and browser-side transaction signing."]
       [:li "Ability to create new organizations — either issuers or trading
            firms."]
       [:li "Ability to create new bonds — bonds can be US Treasury or
            Corporate bonds, denominated in USD, with fixed or floating rates.
            Floating rate bonds are indexed on USD LIBOR."]
       [:li "Ability for participants to play a Market Maker role for a trading
            firm and issue quotes against bonds with bid/ask prices and
            quantities."]
       [:li "Ability for participants to play a Trader role for a trading firm
            and place market or limit orders against bonds."]
       [:li "Ability for participants to view their firm’s holdings,
            settlements, and redemptions."]
       [:li "The system performs distributed automatic quote/order matching in
            time-priority order on next block creation."]
       [:li "Once orders are matched, they can be settled at any time based on
            action by the Trader."]
       [:li "Settlement of a matched order results in asset transfer of bonds
            and USD between the ordering and quoting firms."]
       [:li "If a coupon date or maturity date arrives, an automated receipt
            transaction is generated resulting in USD transfer from issuer to
            bond holder. For maturity redemptions, the face value is exchanged
            for the bond holding."]
       [:li "Real LIBOR rates are inserted as transactions on the blockchain."]
       [:li "In order to simplify the coupon day counting calculations, bonds
            can have coupon frequencies of “Quarterly”, “Monthly”, and “Daily”.
            “Daily” can be used to demonstrate coupon functionality during the
            PoC test period."]]

       [:div
        [:p "We hope you enjoy exploring the capabilities of this proof-of-concept
            platform."]]

       [:div
        [:p "The Intel Sawtooth Lake Team"]]]]))
