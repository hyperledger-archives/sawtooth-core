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

(ns sawtooth.test-common
  (:require [goog.dom :as gdom]
            [clojure.string :as string]))

(defonce is-phantom? (not (nil? (re-find #"PhantomJS" js/window.navigator.userAgent))))

(defn node-list-seq [node-list]
  (when node-list
    (map (fn [index] (aget node-list index)) (range (.-length node-list)))))

(defn elements-by [{:keys [tag cssClass container]}]
  (node-list-seq
    (gdom/getElementsByTagNameAndClass tag cssClass container)))

(def first-element-by (comp first elements-by))

(defn query
  ([selector] (query (gdom/getDocument) selector))
  ([el selector]
   (when el
     (-> el
         (.querySelectorAll selector)
         (node-list-seq)))))

(defn elements
  ([k] (query (name k)))
  ([el k] (query el (name k))))

(def first-element (comp first elements))

(defn first-child [el]
  (when el
    (gdom/getFirstElementChild el)))

(defn children [el]
  (when el
    (node-list-seq (gdom/getChildren el))))

(defn text [el]
  (when el
    (gdom/getTextContent el)))

(defn classes [el]
  (when el
    (-> (.getAttribute el "class")
        (string/split #"\s")
        set)))

(defn insert-container! [container]
  (gdom/appendChild (first-element-by {:tag "body"}) container))

(defn new-container! []
  (let [id (str "container-" (gensym))
        el (gdom/createDom "div" #js {:id id})]
    (insert-container! el)
    (gdom/getElement id)))

(defn remove-container! [container]
  (gdom/removeNode container))
