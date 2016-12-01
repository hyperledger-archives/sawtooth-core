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

(ns sawtooth.components.notification
  (:require [om.core :as om]
            [om.dom :as dom]
            [clojure.string :refer [split-lines]]
            [cljs.core.async :as async :refer [take! put!]]
            [sawtooth.state :refer [notification-action state-change-ch]]
            [sawtooth.components.core :refer [css-transition-group]]))

(def ^:const NOTIFICATION_TTL 3500)

(defn- display-notification [{:keys [timestamp type title message]}]
  (dom/li #js {:key timestamp
               :className (str "notification notification-" (name (or type :info)))}
    (dom/div #js {:className "title"} title)
    (dom/div #js {:className "message"}
             (->> message
                  (split-lines)
                  (map-indexed #(dom/div #js {:key %1} %2))))))

(defn notification-container [data owner]
  (reify

    om/IDisplayName
    (display-name [_] "NotificationContainer")

    om/IWillUpdate
    (will-update [_ next-props next-state]
      (js/setTimeout #(put! state-change-ch {:path [:notification]
                                             :action (fn [notifications] (rest notifications))})
                     NOTIFICATION_TTL))

    om/IRender
    (render [_]
      (dom/div #js {:className "notification-container"}
        (css-transition-group {:component "ul"
                               :transition-name "notification"
                               :transition-enter-timeout 500
                               :transition-leave-timeout 300}
                        (map display-notification (:notification data)))))))

(defn notify!
  "Allows us to send a notification"
  [notification]
  (async/put! state-change-ch (notification-action notification)))
