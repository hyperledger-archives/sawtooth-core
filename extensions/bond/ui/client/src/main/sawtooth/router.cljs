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

(ns sawtooth.router
  (:require [om.core :as om :include-macros true]
            [secretary.core :as secretary]
            [goog.events :as events]
            [goog.history.EventType :as EventType]
            [sawtooth.state :refer [app-state]])
  (:import goog.History)
  (:refer-clojure :exclude [replace]))

(secretary/set-config! :prefix "#")

(defonce history (doto (History.)
                   (goog.events/listen EventType/NAVIGATE
                                       #(-> % .-token secretary/dispatch!))
                   (.setEnabled true)))


(defn current-route []
  (om/ref-cursor (:route (om/root-cursor app-state))))

(defn route-handler [data owner]
  (let [{:keys [current-route route-components not-found]} (om/get-shared owner)
        index (or (om/get-state owner :outlet-index) 0)
        [route _] (om/observe owner (current-route))]
    (if-let [component (get-in (route-components) [route index])]
      (let [route-state (merge (om/get-state owner) {:outlet-index (inc index)})]
        (om/build component data {:state route-state}))
      (om/build not-found nil))))

(defn- strip-hash [path]
  (if (= \# (aget path 0))
    (subs path 1)
    path))

(defn- add-hash [path]
   (if (= "#" (aget path 0))
     path
     (str "#" path)))

(defn- update-history-state! [f path]
  (let [path (add-hash path)
        [base-path _] (clojure.string/split window.location.href #"#")
        url (str base-path path)]
    (f url)
    (secretary/dispatch! path)))

(defn push [path]
  (.setToken history (strip-hash path))
  #_(update-history-state! #(js/history.pushState nil nil %) path))

(defn replace [path]
  (update-history-state! #(js/history.replaceState nil nil %) path))

(defn initialize-route [default-path]
  (let [token (.getToken history)]
    (replace (if (= token "") default-path token))))
