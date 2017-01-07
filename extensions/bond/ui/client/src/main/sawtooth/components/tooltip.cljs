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

(ns sawtooth.components.tooltip
  (:require [goog.events :refer [listenOnce]]
            [goog.dom :as dom]
            [goog.dom.classlist :as classlist]))


; These functions provide support for more complex tooltip interaction than
; mouse hovering, and require the supporting CSS in _tooltip.scss

(def ^:const WRAPPER_CLASS "has-tip")
(def ^:const DISPLAY_CLASS "tip-shown")
(def ^:const TIP_CLASS "tip-text")
(def ^:const DEFAULT_WAIT 3000)

(defn tip-node
  "Creates a tooltip DOM node with specified message text"
  [msg]
  (dom/createDom "span" TIP_CLASS msg))

(defn- setup! [wrapper tip]
  (when tip (dom/appendChild wrapper tip))
  (classlist/addAll wrapper (array WRAPPER_CLASS DISPLAY_CLASS)))

(defn- cleanup!
  ([wrapper tip] (cleanup! wrapper tip false))
  ([wrapper tip remove-wrapper?]
   (when tip (dom/removeNode tip))
   (classlist/remove wrapper DISPLAY_CLASS)
   (when remove-wrapper? (classlist/remove wrapper WRAPPER_CLASS))))

(defn- new-tip-if-not-found! [wrapper msg]
  (when (or (not msg) (not (dom/getElementByClass TIP_CLASS wrapper)))
    (tip-node msg)))

(defn append-basic-tip!
  "Appends a tooltip to a wrapper node, passes a cleanup fn to clear-fn if passed"
  ([wrapper] (append-basic-tip! wrapper nil nil))
  ([wrapper msg-or-clear] (if (string? msg-or-clear)
                            (append-basic-tip! wrapper msg-or-clear nil)
                            (append-basic-tip! wrapper nil msg-or-clear)))
  ([wrapper msg clear-fn]
   (let [tip (new-tip-if-not-found! wrapper msg)
         no-wrapper? (not (classlist/contains wrapper WRAPPER_CLASS))
         no-display? (not (classlist/contains wrapper DISPLAY_CLASS))]
     (setup! wrapper tip)
     (when (and clear-fn (or tip no-display?))
       (clear-fn #(cleanup! wrapper tip no-wrapper?))))))

(defn timed-tip!
  "Adds tooltip to a wrapper node and removes after a wait time"
  ([wrapper] (timed-tip! wrapper nil DEFAULT_WAIT))
  ([wrapper msg-or-wait] (if (string? msg-or-wait)
                           (timed-tip! wrapper msg-or-wait DEFAULT_WAIT)
                           (timed-tip! wrapper nil msg-or-wait)))
  ([wrapper msg wait]
   (append-basic-tip! wrapper msg #(js/setTimeout % wait))))

(defn keyup-tip!
  "Adds tooltip to a wrapper node and removes after any key is pressed"
  ([wrapper] (keyup-tip! wrapper nil))
  ([wrapper msg]
   (append-basic-tip! wrapper msg #(listenOnce js/document "keyup" %))))
