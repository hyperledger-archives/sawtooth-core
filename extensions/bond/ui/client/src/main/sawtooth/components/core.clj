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

(ns sawtooth.components.core)

(defmacro handler
  [fn-args & forms]
  `(fn ~fn-args
     (.preventDefault ~(first fn-args))
     ~@forms))

(defmacro handle-event [& args]
  `(sawtooth.components.core/handler [e#] ~@args))

(defmacro handle-submit
  [owner form-ref & forms]
  `(fn [e#]
    (let [form# (om.core/get-node ~owner ~form-ref)
          ^boolean is-valid?# (.checkValidity form#)]
      (when is-valid?#
        (.preventDefault e#)
        ~@forms)

      (when-not is-valid?#
        (.reportValidity form#)))))

(defmacro when-changed
  "Excutes the given forms when a component with the given
  and state detects a change in the values of the keys"
  [owner state ks & forms]
  `(when (reduce (fn [prev# k#]
                   (let [k-path# (if (vector? k#) k# [k#])]
                     (or prev#
                         (not= (get-in ~state k-path#)
                               (get-in (om.core/get-props ~owner) k-path#)))))
                          false
                          ~ks)
     ~@forms))

(defmacro when-diff
  "Excutes the given forms when the current state and the next state give
  different answers to the given sub-state-fn."
  [owner state sub-state-fn & forms]
  `(when-not (= (~sub-state-fn ~state)
                (~sub-state-fn (om.core/get-props ~owner)))
     ~@forms))

(defmacro when-new-block
  "Executes the given forms when a component with
  the given owner and state detects a change in the
  block."
  [owner state & forms]
  `(when-changed ~owner ~state [:block] ~@forms))
