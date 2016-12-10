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

(ns ^:figwheel-always test-suite.all
  (:require [cljs.test :as test :include-macros true :refer [report]]
            [cljs.pprint :as pprint]
            [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [goog.string :as gstring]
            [figwheel.client :as fw]
            ; Require tests here
            [sawtooth.events :refer [on-content-loaded]]
            sawtooth.http-test
            sawtooth.router-test
            sawtooth.utils-test
            sawtooth.components.core-test
            sawtooth.ledger.keys-test
            sawtooth.ledger.message-test
            sawtooth.ledger.transaction-test
            bond.components.core-test)
  (:import [goog.string StringBuffer]))

(enable-console-print!)

(defonce is-phantom? (not (nil? (re-find #"PhantomJS" js/window.navigator.userAgent))))

(defonce app-state (atom {}))

(defn ^:export run []
  (println "Running tests...")
  (swap! app-state assoc :run-summary nil :run-results [])
  (test/run-tests
    ; add tests to run here
    'sawtooth.http-test
    'sawtooth.router-test
    'sawtooth.utils-test
    'sawtooth.components.core-test
    'sawtooth.ledger.keys-test
    'sawtooth.ledger.transaction-test
    'sawtooth.ledger.message-test
    'bond.components.core-test))

(defn color-favicon-data-url [color]
  (let [cvs (.createElement js/document "canvas")]
    (set! (.-width cvs) 16)
    (set! (.-height cvs) 16)
    (let [ctx (.getContext cvs "2d")]
      (set! (.-fillStyle ctx) color)
      (.fillRect ctx 0 0 16 16))
    (.toDataURL cvs)))

(defn change-favicon-to-color [color]
  (let [icon (.getElementById js/document "favicon")]
    (set! (.-href icon) (color-favicon-data-url color))))

(defn- format-summary-title [{:keys [test pass fail error]}]
 (gstring/format "Ran %s tests containing %s assertions."
                 test
                 (+ pass fail error)))

(defn- format-summary-failures [{:keys [fail error]}]
  (gstring/format "%s failures, %s errors." fail error))

(defmethod report [::test/default :summary] [m]
  (swap! app-state assoc :run-summary m )
  (println)
  (println (format-summary-title m))
  (println (format-summary-failures m))
  (if (< 0 (+ (:fail m) (:error m)))
    (change-favicon-to-color "#d00")
    (change-favicon-to-color "#0d0"))) ;;<<-- change color

(defmethod report [::test/default :begin-test-ns] [m]
  (let [report-map (-> m
                       (select-keys [:ns])
                       (assoc :failures []))]
    (println "\nTesting " (:ns report-map))
    (swap! app-state update-in [:run-results]
           #(conj % report-map))))

(defn- print-comparison [m]
  (let [formatter-fn (or (:formatter (test/get-current-env)) pr-str)]
    (println "expected:" (formatter-fn (:expected m)))
    (println "  actual:" (formatter-fn (:actual m)))))

(defn- last-index [l]
  (dec (count l)))

(def fail-label {:fail "FAIL" :error "ERROR"})

(defn- report-failure [fail-type m]
  (test/inc-report-counter! :fail)
  (println "\n" (fail-label fail-type) "in" (test/testing-vars-str m))
  (when (seq (:testing-contexts (test/get-current-env)))
    (println (test/testing-contexts-str)))
  (when-let [message (:message m)] (println message))
  (print-comparison m)
  (swap! app-state update-in [:run-results (last-index (get @app-state :run-results)) :failures]
         #(conj % {:type fail-type
                   :location (test/testing-vars-str m)
                   :context (test/testing-contexts-str)
                   :message (:message m)
                   :expected (:expected m)
                   :actual (:actual m)})))

(defmethod report [::test/default :begin-test-var] [m]
  (println "\t" (test/testing-vars-str m)))

(defmethod report [::test/default :fail] [m]
  (report-failure :fail m))

(defmethod report [::test/default :error] [m]
  (report-failure :error m))


(defn ^:export test-result []
  (when-let [r (get @app-state :run-summary)]
    (let [{:keys [pass fail error]} r]
      #js {:pass pass
           :fail fail
           :error error
           :succeeded (= 0 (+ fail error))})))

(defn- pprint-html [form]
  (let [sb (StringBuffer.)
        writer (StringBufferWriter. sb)]
    (pprint/write form
                  :pretty true
                  :right-margin 48
                  :stream writer)
    (html
      [:div
       {:dangerouslySetInnerHTML {:__html (.toString sb)}}])))

(defn failure [i {:keys [type location context message expected actual]}]
  (html
    [:div.row {:key i}
     [:div.col-md-offset-1
      [:div [:strong (fail-label type) " in " location]]
      (when context
        [:div context])
      (when message
        [:div message])
      [:table
       [:tbody
        [:tr
         [:th.text-right {:style {"vertical-align" "top"}} "Expected: "]
         [:td (pprint-html expected)]]
        [:tr
         [:th.text-right {:style {"vertical-align" "top"}} "Actual: "]
         [:td (pprint-html actual)]]]]
      [:br]
      ]]))

(defn line-item [i m]
  (html
    [:div {:key i }
     [:div.row  {:class (if (< 0 (count (:failures m)))
                          "text-danger"
                          "text-success")}
      "Testing " (name (:ns m))]
     [:br]
     (map-indexed failure (:failures m))]))

(defn test-app [data owner]
  (om/component
    (html
      [:div.container
       (if-let [run-summary (get data :run-summary)]
         [:div.row
           [:p
            (format-summary-title run-summary)
            [:br]
            (format-summary-failures run-summary)]]
         [:div.row
          [:p "Running..."
           [:br]
           [:br]]])
       [:br]

       [:div
        (map-indexed line-item (get data :run-results))]
       ])))

(when-not is-phantom?

  ; Connect to figwheel to run the tests on updates
  (fw/start {:websocket-url "ws://localhost:3449/figwheel-ws"
             :build-id "test"
             :on-jsload run})

  (on-content-loaded
    (fn []
      (when-let [app-el (. js/document (getElementById "app"))]
        (om/root test-app app-state {:target app-el}))

      (run))))
