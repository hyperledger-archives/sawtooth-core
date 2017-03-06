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

(ns sawtooth.http
  (:require [goog.events :as events]
            [clojure.string :refer [join replace]]
            [cljs.core.async :as async :refer [put!]])
  (:import [goog.net XhrIo]))

(def ^:private http-methods
  {:get "GET"
   :put "PUT"
   :post "POST"
   :delete "DELETE"})

(defn encode-uri-query [s]
  (-> (js/encodeURIComponent s)
      (replace #"%40" "@")
      (replace #"%3A" ":")
      (replace #"%24" "$")
      (replace #"%2C" ",")
      (replace #"%20" "+")))

(defn- make-parameters [query]
  (join "&" (for [[k v] query]
              (str (encode-uri-query (name k)) "=" (encode-uri-query v)))))

(def ^:private content-types
  {:json "application/json; charset=UTF-8"
   :form "application/x-www-form-urlencoded; charset=UTF-8"})

(def ^:private data-formatters
  {:json #(->> % (clj->js) (.stringify js/JSON))
   :form make-parameters})

(defn query-endpoint
  "Takes a URL and a map of query parameters and
  converts them into an endpoint."
  [url query]
  ; filter out nil values
  (let [query (filter #(get % 1) query)]
    (str url (if (empty? query)
               ""
               (str "?" (make-parameters query))))))

(defn ajax
  "Performs an ajax operation.

  Args:
    opts
      :method - one of :get, :put, :post, or :delete; defaults to :get
      :data - post/put data, if needed
      :data-type - one of :json, or :form; defaults to :json
      :close-on-complete? - indicates whether or not the result channel
                            should be closed on completion

    res-ch - the channel on which the results should be placed;
             if one is not provided a channel will be created and returned,
             and closed on completion"
  ([opts] (ajax (dissoc opts :close-on-complete?) (async/chan 1)))
  ([{:keys [method url data data-type headers close-on-complete?]
     :or {method :get close-on-complete? true data-type :json}
     :as opts}
    res-ch]
   (assert url)
   (let [xhr (XhrIo.)
         send-headers (merge {"Content-Type" (data-type content-types)} headers)]
     (events/listen xhr goog.net.EventType.COMPLETE
       (fn [e]
         (if (.isSuccess xhr)
           (put! res-ch
                 {:status (.getStatus xhr)
                  :status-text (.getStatusText xhr)
                  :body (case (-> (or (.getResponseHeader xhr "Content-Type") "")
                                  (.split ";")
                                  first)
                          "application/json" (js->clj (.getResponseJson xhr) :keywordize-keys true)
                          (.getResponseText xhr))
                  :headers (js->clj (.getResponseHeaders xhr))})
           (let [error-code (.getLastErrorCode xhr)
                 error (.getLastError xhr)
                 status (.getStatus xhr)]
             (put!
               res-ch
               {:status (or status (- error-code))
                :status-text error
                :body (ex-info (str "Request to " url " failed")
                               {:error-code error-code :error error})})))
         (when close-on-complete?
           (async/close! res-ch))))

     (. xhr
        (send url (http-methods method)
              (when data ((data-type data-formatters) data))
              (clj->js send-headers))))

   res-ch))

(defn json-xhr [method endpoint data res-ch]
  (ajax {:method method :url endpoint :data data :data-type :json} res-ch))
