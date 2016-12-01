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

(ns sawtooth.state
  (:require [cljs.core.async :as async :refer [<!]]
            [taoensso.timbre :as timbre :refer-macros [errorf]])
  (:require-macros [cljs.core.async.macros :refer [go-loop]]))

(def ^:private initial-state {:notification []
                              :route []})

(defonce app-state (atom initial-state))

(defonce state-change-ch (async/chan))

(go-loop []
  (when-let [{:keys [path value action f args] :as evt} (<! state-change-ch)]
    (try
      (cond
        f (apply swap! app-state f args)
        action (swap! app-state update-in path action)
        :default (swap! app-state assoc-in path value))
    (catch :default e
      (errorf e "Unknown error occurred on state while processing %s" evt)))
    (recur)))

(defn reset-state! []
  (reset! app-state initial-state))

(defn notification-action [notification]
  (let [timestamped (assoc notification :timestamp (.now js/Date))]
    {:path [:notification]
     :action #(into [timestamped] %)}))
