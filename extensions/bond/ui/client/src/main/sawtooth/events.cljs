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

(ns sawtooth.events
  (:require [goog.object :as gobj]))

(defn on-content-loaded
  "Triggers the given function on content loaded."
  [f]
  ; Run the tests the first time the page is loaded
  (.addEventListener js/document "DOMContentLoaded" f))

(defn trigger-event!
  "Triggers an event of 'type' on the passed element"
  [elem type]
  (cond
    (and  (= type "click") (gobj/get elem "click")) (.click elem)

    :default
    (let [e (.createEvent js/window.document "HTMLEvents")]
      (.initEvent e type true false)
      (.dispatchEvent elem e))))
