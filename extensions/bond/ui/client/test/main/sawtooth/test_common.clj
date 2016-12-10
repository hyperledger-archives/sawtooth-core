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

(ns sawtooth.test-common)

(defmacro with-container [container & forms]
  `(let [~container (sawtooth.test-common/new-container!)]
     (try
     ~@forms
     (finally
      (sawtooth.test-common/remove-container! ~container)))))

(defn- do-timeout [timeout forms]
  `(js/setTimeout (fn [] ~@forms) ~timeout))

(defmacro defer [timeout & forms]
  (do-timeout timeout forms))

(defmacro next-tick [& forms]
  (do-timeout 0 forms))

(defmacro <* [ch timeout-ms]
  `(let [src-ch# ~ch ; force `ch` form to evaluate
         [result# result-ch#] (cljs.core.async/alts! [src-ch# (cljs.core.async/timeout ~timeout-ms)])]
     (if (= result-ch# src-ch#)
       result#
       :timed-out)))

;
; From https://nvbn.github.io/2014/11/05/protocols-for-testing/
(defn- ^:no-doc with-reset-once
  [[a-var a-val] body]
  `(let [prev-val# [~a-var]]
     (set! ~a-var ~a-val)
     (try (do ~@body)
          (catch js/Error e# (throw e#))
          (finally (set! ~a-var (first prev-val#))))))

(defmacro with-reset
  [bindings & body]
  (let [wrapper-fn (->> (partition-all 2 bindings)
                        (map #(partial with-reset-once %))
                        (apply comp))]
    (wrapper-fn body)))
