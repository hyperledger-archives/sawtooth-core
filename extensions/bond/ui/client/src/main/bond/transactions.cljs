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

(ns bond.transactions
  (:require [cljs.core.async :as async]
            [sawtooth.ledger.message :as msg]
            [sawtooth.vendor :refer [bitcoin]]
            [sawtooth.utils :refer [without-nil]]
            [sawtooth.components.notification :refer [notify!]]
            [sawtooth.ledger.keys :refer [address]]
            [sawtooth.ledger.transaction :as txn
             :include-macros true])
  (:require-macros [cljs.core.async.macros :refer [go]]))


(def ^:const bond-txn-family "/BondTransaction")
(def ^:const bond-msg-type "/Bond/Transaction")

(def ^:const bond-holding-qty 1000000)
(def ^:const usd-holding-qty 1000000000)

(msg/set-ratio-fields! #{:CouponRate :Amount})


  ;;  HELPERS  ;;

(defn- nonce []
  (let [chars (map char (range 65 123))]
    (->> (repeatedly #(rand-nth chars))
         (take 16)
         (reduce str))))

(defn- make-object-id
  [txn-update]
  (->> txn-update
       msg/->signable
       clj->js
       (.hash bitcoin)))

(defn- with-object-id [txn-update]
  (assoc txn-update :ObjectId (make-object-id txn-update)))

(defn- make-update
  ([update] (make-update {} update))
  ([template update]
   (-> (merge template update)
       without-nil)))

(defn- update-with-id
  ([update] (update-with-id {} update))
  ([template update]
   (with-object-id (make-update template update))))

(defn- make-bond-txn [update & deps]
  (msg/make-transaction bond-txn-family [update] (vec deps)))

(defn- send-bond-txn
  ([signing-identity update] (send-bond-txn signing-identity update identity))
  ([signing-identity update on-done-fn]
   (txn/send-transaction
     signing-identity
     bond-msg-type
     (make-bond-txn update)
     {:key-id (address signing-identity)}
     on-done-fn)))

(defn- notify-start []
  (notify! {:title "Submitting Chained Transactions"
            :message "Please wait a moment while your initial transactions resolve."}))


  ;;  PARTICIPANTS  ;;

(defn create-participant
  [signing-identity username firm-id on-done-fn]
  (let [participant-update
        (update-with-id
          {:FirmId firm-id
           :UpdateType "CreateParticipant"
           :Username username})

        auth-update
        (make-update
          {:UpdateType "UpdateOrganizationAuthorization"
           :ObjectId firm-id
           :Action "add"
           :ParticipantId (:ObjectId participant-update)
           :Role "marketmaker"})]

    (txn/send-chained-transactions
      signing-identity
      bond-msg-type
      [first-id [(make-bond-txn participant-update)
                 {:key-id (address signing-identity)}]
       _ (make-bond-txn auth-update first-id)]
      on-done-fn)))

(defn update-participant
  [signing-identity {:keys [object-id username firm-id]}]
  (send-bond-txn
    signing-identity
    (make-update
      {:UpdateType "UpdateParticipant"
       :ObjectId object-id
       :Username username
       :FirmId firm-id})))

(defn update-authorization
  [signing-identity firm-id participant-id action role]
  {:pre [(#{:marketmaker :trader "marketmaker" "trader"} role)
         (#{:add :remove "add" "remove"} action)]}
  (send-bond-txn
    signing-identity
    (make-update
      {:UpdateType "UpdateOrganizationAuthorization"
       :ObjectId firm-id
       :Action (name action)
       :ParticipantId participant-id
       :Role (name role)})))

(defn modify-authorization
  "Removes and adds firm authorization to avoid errors with duplicate auths"
  ([signing-identity participant-id old-firm new-firm old-role new-role]
   (modify-authorization signing-identity participant-id old-firm new-firm old-role new-role identity))
  ([signing-identity participant-id old-firm new-firm old-role new-role on-done-fn]
  {:pre [(#{:marketmaker :trader "marketmaker" "trader"} old-role)
         old-firm]}
  (let [new-firm (or new-firm old-firm)
        new-role (or new-role old-role)

        auth-template
        {:UpdateType "UpdateOrganizationAuthorization"
         :ParticipantId participant-id}

        remove-update
        (make-update
          auth-template
          {:Action (name :remove)
           :ObjectId old-firm
           :Role old-role})

        add-update
        (make-update
          auth-template
          {:Action (name :add)
           :ObjectId new-firm
           :Role new-role})]

    (txn/send-chained-transactions
      signing-identity
      bond-msg-type
      [first-id (make-bond-txn remove-update)
       _ (make-bond-txn add-update first-id)]
      on-done-fn))))


  ;;  ORGANIZATIONS  ;;

(defn create-issuing-org
  [signing-identity {:keys [name industry ticker]} on-done-fn]
  (send-bond-txn
    signing-identity
    (update-with-id
      {:UpdateType "CreateOrganization"
       :Name name
       :Industry industry
       :Ticker ticker})
    on-done-fn))

(defn create-trading-org
  ([signing-identity trading-org]
   (create-trading-org signing-identity trading-org [] identity))
  ([signing-identity trading-org bonds-or-done-fn]
   (if (coll? bonds-or-done-fn)
     (create-trading-org signing-identity trading-org bonds-or-done-fn identity)
     (create-trading-org signing-identity trading-org [] bonds-or-done-fn)))
  ([signing-identity {:keys [name industry pricing-source authorization]} bonds on-done-fn]
   (let [participant-id (first authorization)
         org-update
         (update-with-id
           {:UpdateType "CreateOrganization"
            :Name name
            :Industry industry
            :PricingSource pricing-source
            :Authorization authorization})

         participant-update
         (make-update
           {:UpdateType "UpdateParticipant"
            :ObjectId (:ParticipantId participant-id)
            :FirmId (:ObjectId org-update)})

         holding-template
         {:UpdateType "CreateHolding"
          :OwnerId (:ObjectId org-update)}

         usd-update
         (update-with-id
           holding-template
           {:AssetType "Currency"
            :AssetId "USD"
            :Amount usd-holding-qty})

         bond-updates
         (mapv #(update-with-id
                  holding-template
                  {:AssetType "Bond"
                   :AssetId (:id %)
                   :Amount bond-holding-qty})
               bonds)]

    ; After org and participant are updated, add holdings in all bonds for org
    (notify-start)
    (txn/send-chained-transactions
      signing-identity
      bond-msg-type
      [org-id (make-bond-txn org-update)
       prt-id (make-bond-txn participant-update org-id)
       holding-id (make-bond-txn usd-update org-id prt-id)
       _ [(msg/make-transaction bond-txn-family
                                bond-updates
                                [org-id prt-id])
          {:creator-id participant-id}]]
      on-done-fn))))

(defn update-organization
  [signing-identity {:keys [object-id name industry ticker pricing-source]}]
  (send-bond-txn
    signing-identity
    (make-update
      {:UpdateType "UpdateOrganization"
       :ObjectId object-id
       :Name name
       :Industry industry
       :Ticker ticker
       :PricingSource pricing-source})))


  ;;  BUYING AND SELLING BONDS  ;;

(defn create-bond
  ([signing-identity participant-id issuer bond]
   (create-bond signing-identity participant-id issuer bond [] identity))
  ([signing-identity participant-id issuer bond firms-or-done-fn]
   (if (coll? firms-or-done-fn)
     (create-bond signing-identity participant-id issuer bond firms-or-done-fn identity)
     (create-bond signing-identity participant-id issuer bond [] firms-or-done-fn)))
  ([signing-identity participant-id issuer bond firms on-done-fn]
   (let [bond-update
         (update-with-id
           {:UpdateType "CreateBond"
            :Issuer (:ticker issuer)
            :Isin (:isin bond)
            :Cusip (:cusip bond)
            :AmountOutstanding (:amount-outstanding bond)
            :CorporateDebtRatings {"Fitch" (get-in bond [:corporate-debt-ratings :fitch])
                                  "Moody's" (get-in bond [:corporate-debt-ratings :moodys])
                                  "S&P" (get-in bond [:corporate-debt-ratings :s&p])}
            :CouponBenchmark (:coupon-benchmark bond)
            :CouponRate (:coupon-rate bond)
            :CouponType (:coupon-type bond)
            :CouponFrequency (:coupon-frequency bond)
            :FirstCouponDate (:first-coupon-date bond)
            :FirstSettlementDate (:first-settlement-date bond)
            :MaturityDate (:maturity-date bond)
            :FaceValue (:face-value bond)})

         holding-updates
         (mapv #(update-with-id
                  {:UpdateType "CreateHolding"
                   :OwnerId (:id %)
                   :AssetType "Bond"
                   :AssetId (:ObjectId bond-update)
                   :Amount bond-holding-qty})
               firms)]

    ; After bond is created, add holdings in it to all trading firms
    (notify-start)
    (txn/send-chained-transactions
      signing-identity
      bond-msg-type
      [bond-txn-id [(msg/make-transaction bond-txn-family [bond-update])
                    {:creator-id participant-id}]
       _ [(msg/make-transaction bond-txn-family
                                holding-updates
                                [bond-txn-id])
          {:creator-id participant-id}]]
      on-done-fn))))

(defn create-quote
  [signing-identity participant-id
   {:keys [firm isin cusip bid-price bid-qty ask-price ask-qty]} on-done-fn]
   (txn/send-transaction
     signing-identity
     bond-msg-type
     (make-bond-txn
       (update-with-id
        {:UpdateType "CreateQuote"
         :Firm firm
         :Isin isin
         :Cusip cusip
         :BidPrice bid-price
         :BidQty bid-qty
         :AskPrice ask-price
         :AskQty ask-qty}))
    {:creator-id participant-id}
    on-done-fn))

(defn create-order
  [signing-identity participant-id {:keys [action order-type firm-id isin cusip quantity price yield]} on-done-fn]
  (let [order-template
        {:UpdateType "CreateOrder"
         :Nonce (nonce)
         :Action action
         :OrderType order-type
         :FirmId firm-id
         :Isin isin
         :Cusip cusip
         :Quantity quantity}

        order-update
        (if (= "Market" order-type)
          (update-with-id order-template)
          (update-with-id
            order-template
            {:LimitPrice price
             :LimitYield yield}))]

   (txn/send-transaction
     signing-identity
     bond-msg-type
     (make-bond-txn order-update)
    {:creator-id participant-id} on-done-fn)))

(defn create-settlement
  ([signing-identity order-id]
   (create-settlement signing-identity order-id identity))
  ([signing-identity order-id on-done-fn]
   (send-bond-txn
     signing-identity
     (update-with-id
       {:UpdateType "CreateSettlement"
        :OrderId order-id})
     on-done-fn)))
