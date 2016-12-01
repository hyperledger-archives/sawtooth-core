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

(ns bond.service.participant
  (:require [cljs.core.async :as async]
            [sawtooth.state :refer [state-change-ch notification-action reset-state!]]
            [sawtooth.config :refer [base-url]]
            [sawtooth.service.common :as svc]
            [sawtooth.http :as http]
            [sawtooth.ledger.keys :as keys]
            [taoensso.timbre :as timbre
             :refer-macros [debug debugf info infof]])
  (:require-macros [cljs.core.async.macros :refer [go]]))


(def ^:const API_URI "/api/bond/participants")

(defn participant!
  "Fetches a participant from server"
  ([address] (participant! address nil identity))
  ([address query-or-not-found]
   (if (map? query-or-not-found)
     (participant! address query-or-not-found identity)
     (participant! address nil query-or-not-found)))
  ([address query on-not-found]
  (go
    (let [res-ch (http/ajax {:url (http/query-endpoint
                                    (str base-url API_URI "/" address)
                                    (select-keys query [:fetch-firm]))})
          {:keys [status body]} (<! res-ch)]
      (cond (= 404 status) (on-not-found)
            (= 200 status) (>! state-change-ch {:path [:participant] :value body})
            :default (>! state-change-ch {:type :error
                                          :title "Unknown Server Error"
                                          :message "An error occured while attempting
                                                   to fetch the participant from the server."}))))))

(defn participants!
  "Fetches all basic particpant info from server and saves it to the app-state"
  ([] (participants! nil))
  ([query]
   (svc/fetch-json!
     API_URI
     (select-keys query [:username])
     {:path [:participants]
      :on-error {:title "Unable to fetch participants"
                 :message "An unknown error occured while attempting
                          to fetch participants!"}})))

(defn sign-out!
  "Signs a participant out."
  [on-done]
  (keys/clear-wif!)
  (reset-state!)
  (on-done))
