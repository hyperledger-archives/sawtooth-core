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

(ns sawtooth.service.block
  (:require [cljs.core.async :as async :refer [take! put!]]
            [sawtooth.config :refer [socket-location]]
            [sawtooth.state :refer [app-state state-change-ch notification-action]]
            [sawtooth.service.common :as service]
            [taoensso.timbre :as timbre
             :refer-macros [debug debugf info infof]]
            [sawtooth.vendor :as vendor :refer [socket]]))

(defonce ^:private current-socket (atom nil))

(defn- make-socket [url]
  (.io socket url))

(defn connect-block-monitor []
  (info "Connecting block monitor...")
  (let [s (make-socket (socket-location))]
    (reset! current-socket s)
    (.on @current-socket "chain_info"
         #(let [block-info (js->clj % :keywordize-keys true)]
            (when-not (= (:blockid block-info) (get-in @app-state [:block :blockid]))
              (debugf "Received block %s (%s)" (:blocknum block-info) (:blockid block-info))

              ; notify the user on subsequent updates
              (when (:block @app-state)
                #_(put! state-change-ch
                      (notification-action {:type :info
                                            :title "Block Update"
                                            :message "The block has updated!"})))

              (put! state-change-ch {:path [:block]
                                     :value block-info}))))))

(defn disconnect-block-monitor []
  (info "Disconnecting block monitor...")
  (when-let [s @current-socket]
    (.disconnect s)
    (reset! current-socket nil)))

(defn chain-info []
  (service/fetch-json!
    "/api/ledger/chain"
    {:path [:chain :info]
     :on-error {:title "Unable to Load Chain Info"
                :message "Failed to load the current status of the chain"}}))

(defn transactions [query]
  (service/fetch-json!
    "/api/ledger/transactions"
    query
    {:path [:chain :transactions]
     :on-error {:title "Unable to Load Transaction History"
                :message "Failed to load the transaction history
                         due to an unknown server error."}}))

(defn transaction-detail [id]
  (service/fetch-json!
    (str "/api/ledger/transactions/" id)
    {:xform (fn [txn]
              {:path [:chain :transaction-details]
               :action #(conj % txn)})
     :on-error {:title "Unable Load Trasaction"
                :message (str "Failed to load trasaction " id
                              " due to an unkown server error.")}}))

(defn pop-transaction-detail []
  (put! state-change-ch {:path [:chain :transaction-details]
                         :action rest}))

(defn clear-chain-info []
  (service/clear-path! [:chain]))

(defn clear-transaction-details []
  (service/clear-path! [:chain :transaction-details]))
