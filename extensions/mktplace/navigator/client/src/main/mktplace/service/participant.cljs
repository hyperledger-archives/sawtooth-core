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
(ns mktplace.service.participant
  (:require [cljs.core.async :as async :refer [take! put!]]
            [goog.string :as gstring]
            [sawtooth.config :refer [base-url]]
            [sawtooth.http :as http]
            [sawtooth.ledger.keys :as keys]
            [sawtooth.router :as router]
            [sawtooth.service.common :as service]
            [sawtooth.state :refer [app-state state-change-ch
                                    reset-state! notification-action]]
            [sawtooth.store :as store]
            [mktplace.routes :as routes]
            [mktplace.transactions])
  (:require-macros [cljs.core.async.macros :refer [go]]))

(def ^:const PARTICIPANT_ENDPOINT_TEMPLATE
  (str base-url "/api/mktplace/participants/%s"))

(def ^:const PARTICIPANTS_ENDPOINT
  "/api/mktplace/participants")

(defn current-participant-id
  "The id of the currently logged-in participant"
  []
  (store/get-data :participant-id))

(defn set-current-participant!
  "Sets the current participant"
  [participant]
  (store/save-data! :participant-id (:id participant)))

(defn sign-out
  "Signs out the current user"
  []
  (store/remove-data! :participant-id)
  (keys/clear-wif!)
  (reset-state!)
  (router/push (routes/intro-path)))

(defn- handle-failure
  "Sets the state value of the key to nil and notifies the user of a failure"
  [k msg]
  (put! state-change-ch {:path [k]
                         :value nil})
  (put! state-change-ch
        (notification-action {:type :error
                              :title "An Error Occurred"
                              :message msg})))

(defn register
  "registers a participant with the given name and description, associated with a
  signing-identity and an address"
  [signing-identity address name desc]
  (mktplace.transactions/register-participant
    signing-identity address name desc #(router/push (routes/home-path))))

(defn- handle-incoming-participant [signing-identity party]
  (set-current-participant! party)
  (when (not (:account party))
    (mktplace.transactions/register-account signing-identity party))
  (put! state-change-ch {:path [:participant]
                         :value party}))

(defn participant
  "Loads the participant for the given id into the app-state
  at the path [:participant]"
  [id]
  (let [res-ch (async/chan 1)
        url (gstring/format PARTICIPANT_ENDPOINT_TEMPLATE id)]
    (http/json-xhr :get url nil res-ch)
    (take! res-ch (fn [{:keys [status body]}]
                    (if (= 200 status)
                      (handle-incoming-participant
                        (keys/get-key-pair) body)
                      (handle-failure
                        :participant "Unable to load participant!"))))))

(defn- load-participant-into
  [id path msg-type]
  (service/fetch-json!
    (str PARTICIPANTS_ENDPOINT "/" id)
    {:path path
     :on-error {:message (gstring/format "Unable to load %s participant." msg-type)
                :title "An Error Occurred"}}))

(defn as-participant
  "Loads a view participant into the app-state at the path [:view-participant].
  This participant is used to alter the read-only views of the system."
  [id]
  (load-participant-into id [:view-participant] "view"))

(defn as-self
  "Returns the view to the authenticated user."
  []
  (service/clear-path! [:view-participant]))

(defn transfer-target-participant
  "Loads a target participant for the given id into the app-state at
  the path [:transfer :target-participant]."
  [id]
  (load-participant-into id [:transfer :target-participant] "target"))

(defn clear-transfer-target-participant
  "Clears the target participan in the app-state at [:transfer :target-participant]."
  []
  (service/clear-path! [:transfer :target-participant]))


(defn- handle-incoming-wallet-participant [address party]
  (cond
    (:pending party) (put! state-change-ch {:path [:participant] :value party})
    (and party (:id party)) (participant (:id party))
    :default (router/push (routes/create-participant-path {:address address}))))

(defn participant-by-address
  "Loads the participant associated with an existing wallet into the app-state"
  [address]
  (let [res-ch (async/chan)]
    (go
      (let [_ (http/json-xhr :post
                             (str base-url PARTICIPANTS_ENDPOINT)
                             {:address address} res-ch)
            {:keys [status body]} (<! res-ch)]

        (if (= 200 status)
          (handle-incoming-wallet-participant address body)
          (handle-failure :participant
                          "Unable to load participant!"))))))

(defn participants
  "Loads the names and ids of all the participants into the app-state."
  []
  (service/fetch-json!
    PARTICIPANTS_ENDPOINT
    {:path [:participants]
     :on-error {:message "Unable to load participants!"
                :title "An Error Occurred"}}))

(defn is-fully-provisioned?
  "Indicates whether or not a participant is considered fully provisioned."
  [participant]
  (and (not (:pending participant))
       (:account participant)
       (not (get-in participant [:account :pending]))))
