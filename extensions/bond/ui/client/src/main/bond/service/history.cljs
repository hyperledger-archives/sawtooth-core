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

(ns bond.service.history
  (:require [sawtooth.service.common :as service]
            [goog.string :as gstring]))

(def ^:const API_URI_PATTERN "/api/bond/organizations/%s/%s")

(defn load-firm-history!
  [firm-id opts base-path]
   (service/fetch-json!
     (gstring/format API_URI_PATTERN firm-id (name base-path))
     (select-keys opts [:page :limit])
     {:path [base-path]
      :on-error {:title (str "Unable to load " (name base-path))
                 :message (gstring/format
                            "Unable to load %s due
                            to an unknown server error."
                            (name base-path))}}))

(defn load-receipts!
  ([firm-id] (load-receipts! firm-id nil))
  ([firm-id opts]
   (load-firm-history! firm-id opts :receipts)))

(defn clear-receipts!
  []
  (service/clear-path! [:receipts]))

(defn load-settlements!
  ([firm-id] (load-settlements! firm-id nil))
  ([firm-id opts]
   (load-firm-history! firm-id opts :settlements)))

(defn clear-settlements! []
  (service/clear-path! [:settlements]))
