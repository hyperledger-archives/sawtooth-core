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

(ns sawtooth.store)

(defonce ^:private cache (atom {}))

(defn get-data
  "Gets string data that has been stored in localStorage."
  ([k] (get-data k nil))
  ([k default-value]
   (if-let [v (get @cache k)]
     v
     (if-let [v (aget js/window.localStorage (name k))]
       (get (swap! cache assoc k v) k)
       default-value))))

(defn save-data!
  "Saves string data into localStorage."
  ([k v]
   {:pre [(string? v)]}
   (swap! cache assoc k v)
   (.setItem js/window.localStorage (name k) v)))

(defn remove-data!
  "Removes data from localStorage."
  ([k]
   (swap! cache dissoc k)
   (.removeItem js/window.localStorage (name k))))
