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

(ns bond.service.quote
  (:require [sawtooth.service.common :as service]
            [goog.string :as gstring]))

(def ^:const API_URI "/api/bond/quotes/")

(defn quotes!
  "Fetch a bond and all quotes made on it from server"
  ([participant-id bond-id] (quotes! participant-id bond-id nil))
  ([participant-id bond-id opts]
   (service/fetch-json!
     (str API_URI bond-id)
     (select-keys opts [:page :limit])
     {:path [:quotes-info]
      :headers {:participant-id participant-id}
      :on-error {:title "Unable To Fetch Quotes"
                 :message "An unknown error occurred while
                           while attempting fetch quotes"}})))

(defn clear-quotes!
  []
  (service/clear-path! [:quotes-info]))

(defn latest-quote!
  ([bond-id pricing-source]
   {:pre [(not (nil? bond-id))
          (not (nil? pricing-source))]}
   (service/fetch-json!
     (str "/api/bond/bonds/" bond-id "/latest-quote/" pricing-source)
     {:path [:latest-quote]
      :on-error {:title "Unable to Fetch Latest Quote"
                 :message (gstring/format
                            "An unknown error occurred while
                            trying to fetch the latest quote for %s
                            and %s."
                            bond-id pricing-source)}})))

(defn clear-latest-quote!
  []
  (service/clear-path! [:latest-quote]))
