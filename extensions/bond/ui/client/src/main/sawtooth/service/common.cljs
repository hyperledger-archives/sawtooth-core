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

(ns sawtooth.service.common
  (:require [cljs.core.async :as async :refer [take! put!]]
            [sawtooth.state :refer [state-change-ch notification-action]]
            [sawtooth.config :refer [base-url]]
            [sawtooth.http :as http]
            [taoensso.timbre :as timbre
             :refer-macros [debug debugf info infof]]))

(defn- on-fetch-success-fn [xform make-notification-fn]
  (fn [{status :status body :body}]
    (if (= status 200)
      (put! state-change-ch (xform body))
      (put! state-change-ch
            (notification-action (make-notification-fn))))))

(defn- on-error-notification [endpoint on-error]
  (merge {:type :error
          :title "Fetch Failed"
          :message (str "Unable to fetch " endpoint)}
         on-error))

(defn fetch-json!
  "Fetches json at the given endpoint. Either a result transform
  or a resulting path on the state must be provided in the opts
  (but not both)."
  ([endpoint opts] (fetch-json! endpoint nil opts))
  ([endpoint query {:keys [xform path on-error headers]}]
   (assert (and (or xform path)
                (not (and xform path))))
   (let [xform (or xform (fn [body] {:path path :value body}))
         res-ch (async/chan 1
                            (map (on-fetch-success-fn
                                   xform
                                   #(on-error-notification endpoint on-error)))
                            (fn [e] (notification-action
                                      {:type :error
                                       :title "Exception!"
                                       :message e})))
         url (str base-url (if query (http/query-endpoint endpoint query) endpoint))]
      (async/pipe res-ch state-change-ch false)
      (http/ajax {:url url :headers headers} res-ch))))

(defn set-path! [path value]
  (put! state-change-ch {:path path :value value}))

(defn clear-path!
  "Clears the state at the given path, with an optional clear-value."
  ([path] (clear-path! path nil))
  ([path clear-value]
   (put! state-change-ch {:path path :value clear-value})))
