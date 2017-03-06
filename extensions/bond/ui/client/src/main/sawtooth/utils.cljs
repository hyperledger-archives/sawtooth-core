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

(ns sawtooth.utils)

(defn index-of
  [pred coll]
  (let [f (if (or (fn? pred) (ifn? pred))
            pred
            #(= pred %))]
    (->> coll
         (map-indexed vector)
         (some (fn [[idx item]] (if (f item) idx))))))

(defn first-by
  [coll k v]
  (when v
    (->> coll
         (filter #(= (get % k) v))
         first)))

(defn firstk
  ([coll id k] (firstk coll :id id k))
  ([coll idk id k]
   (get (first-by coll idk id) k)))

(defn without-nil
  "Returns a map with all of the nil values removed."
  [m]
  (when m
    (reduce-kv
      (fn [m k v]
        (cond
          (map? v) (assoc m k (without-nil v))
          v (assoc m k v)
          :default m))
      {}
      m)))

(defn log
  "A basic console log, in order to take advantage of devtools
  console formatting"
  [& xs]
  (if-not (empty? xs)
    (.apply (.-log js/console) js/console (apply array xs))
    (.log js/console)))

; Returns a keyword corresponding to the user's browser
(def browser (memoize (fn []
  (let [user-agent (.-userAgent js/navigator)
        agent-contains #(re-find (re-pattern %) user-agent)]
        (cond (agent-contains "Firefox") :firefox
              (agent-contains "OPR") :opera
              (or (agent-contains "MSIE") (agent-contains "Trident")) :ie
              ; Order important: Edge lists Chrome/Safari, Chrome lists Safari
              (agent-contains "Edge") :edge
              (agent-contains "Chrome") :chrome
              (agent-contains "Safari") :safari
              :default nil)))))
