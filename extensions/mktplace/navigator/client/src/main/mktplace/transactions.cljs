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
(ns mktplace.transactions
  (:require [sawtooth.ledger.message :as msg]
            [sawtooth.ledger.transaction :as txn
             :include-macros true]))

(defonce ^:const mktplace-txn-family "/MarketPlaceTransaction")
(defonce ^:const mktplace-msg-type "/mktplace.transactions.MarketPlace/Transaction")

(defn- find-dependencies [txn-update]
  (->> txn-update
       (filter (fn [[k v]]
                 (re-find #".*Id.*" (name k))))
       (map (fn [[k v]] v))
       flatten
       sort
       distinct
       vec))

(defn- make-mktplace-txn [mktplace-update]
  (msg/make-transaction
    mktplace-txn-family
    [mktplace-update]
    (find-dependencies mktplace-update)))

(defn- holding-id-for-asset [participant {asset-id :asset}]
  (->>
    participant
    :holdings
    (filter #(= asset-id (:asset %)))
    first
    :id))

(defn- holding-update-register [participant holding]
  (let [participant-id (get participant :id)
        account-id (get-in participant [:account :id])

        {holding-name :name description :description
         asset :asset holding-count :count}
        holding

        asset-id (if (map? asset) (:id asset) asset)]
    (make-mktplace-txn
      {:UpdateType "RegisterHolding"
       :CreatorId participant-id
       :Name (or holding-name "")
       :Description (or description "")
       :AccountId account-id
       :AssetId asset-id
       :Count (or holding-count 0)})))

(defn exchange
  "Executes an exchange for a participant on the given offer."
  ([signing-identity participant initial-liability final-liability offers initial-count]
   (exchange signing-identity participant initial-liability final-liability offers initial-count nil))
  ([signing-identity participant initial-liability final-liability offers initial-count on-done-fn]
   (let [annotations {:creator (:id participant)}]
     (txn/send-chained-transactions
       signing-identity
       mktplace-msg-type
       [final-liability-id (cond
                             ; Is it an existing, full holding? Use its id
                             (and (map? final-liability) (:id final-liability))
                             (:id final-liability)

                             ; Is it  a new holding? Let's create it.
                             (map? final-liability)
                             [(holding-update-register participant final-liability)
                              annotations]

                             ; it's probably a holding id
                             :default final-liability)
       _ [(make-mktplace-txn
            {:UpdateType "Exchange"
             :FinalLiabilityId final-liability-id
             :InitialLiabilityId (if (map? initial-liability)
                                   (:id initial-liability)
                                   initial-liability)
             :OfferIdList (mapv :id offers)
             :InitialCount initial-count})
          annotations]]
       on-done-fn))))

(defn- register-asset-type [participant-id {:keys [name description restricted]}]
  (make-mktplace-txn
    {:UpdateType "RegisterAssetType"
     :CreatorId participant-id
     :Name (or name "")
     :Description (or description "")
     :Restricted (if-not (nil? restricted) restricted true)}))

(defn register-asset [signing-identity participant asset-type-id-or-map asset]
  (let [participant-id (:id participant)
        {:keys [name description restricted consumable divisible]} asset]
    (txn/send-chained-transactions
      signing-identity
      mktplace-msg-type
      [asset-type-id (if (map? asset-type-id-or-map)
                       [(register-asset-type participant-id asset-type-id-or-map)
                        {:creator participant-id}]
                       asset-type-id-or-map)
      _ (make-mktplace-txn
          {:UpdateType "RegisterAsset"
           :CreatorId participant-id
           :Restricted (if-not (nil? restricted) restricted true)
           :Consumable (if-not (nil? consumable) consumable true)
           :Divisible (if-not (nil? divisible) divisible false)
           :Name (or name "")
           :Description (or description "")
           :AssetTypeId asset-type-id})]
      nil)))

(defn register-holding
  "Registers a holding for a participant.

  Params:
  - signing-identity - the wallet used for signing.
  - participant - the participant registering the holding
  - holding - a map of :name, :description :asset and :count"
  [signing-identity participant holding]
  (txn/send-transaction
    signing-identity
    mktplace-msg-type
    (holding-update-register participant holding)
    {:creator (:id participant)}))

(defn register-participant
  "registers a participant with the given name and description, associated with a
  signing-identity and an andress"
  [signing-identity address name desc on-done-fn]
  (txn/send-transaction
    signing-identity
    mktplace-msg-type
    (make-mktplace-txn
      {:UpdateType "RegisterParticipant"
       :Name (or name "")
       :Description (or desc "")})
    {:address address}
    on-done-fn))

(defn register-account [signing-identity participant]
  (let [{participant-id :id name :name} participant]
    (txn/send-transaction
      signing-identity
      mktplace-msg-type
      (make-mktplace-txn
        {:UpdateType "RegisterAccount"
         :CreatorId participant-id
         :Name (str "/account/" name)
         :Description ""})
      {:creator participant-id})))

(defn register-sell-offer
  "Registers a sell offer"
  ([signing-identity participant offer]
   (register-sell-offer signing-identity participant offer identity))
  ([signing-identity {participant-id :id} offer on-done-fn]
  (let [{:keys [name description input input-count output output-count
                minimum maximum execution]} offer]

    (assert (integer? input-count))
    (assert (integer? output-count))
    (assert (string? input))
    (assert (string? output))

    (txn/send-transaction
      signing-identity
      mktplace-msg-type
      (make-mktplace-txn
        {:UpdateType "RegisterSellOffer"
         :CreatorId participant-id
         :Name (or name "")
         :Description (or description "")
         :InputId input
         :OutputId output
         :Ratio (/ output-count input-count)
         :Minimum minimum
         :Maximum maximum
         :Execution execution})
      {:creator participant-id}
      on-done-fn))))

(defn unregister-sell-offer
  "Unregisters a sell offer"
  ([signing-identity participant offer]
   (unregister-sell-offer signing-identity participant offer identity))
  ([signing-identity {participant-id :id} {offer-id :id} on-done-fn]
  (txn/send-transaction
    signing-identity
    mktplace-msg-type
    (make-mktplace-txn
      {:UpdateType "UnregisterSellOffer"
       :ObjectId offer-id
       :CreatorId participant-id})
    {:creator participant-id}
    on-done-fn)))
