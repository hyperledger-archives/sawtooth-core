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
(ns mktplace.service.asset
  (:require [cljs.core.async :as async :refer [take! put!]]
            [sawtooth.service.common :as service])
  (:require-macros [cljs.core.async.macros :refer [go]]))

(defn- not-bootstrap-asset [{:keys [_fqname]}]
   (not (and _fqname (re-find #"//marketplace/asset/validation-token" _fqname))))

(defn- not-boostrap-asset-type [{:keys [_fqname]}]
  (not (and _fqname (re-find #"//marketplace/asset-type/participant" _fqname))))

(def ^:const ASSETS_ENDPOINT "/api/mktplace/assets")

(defn assets []
  (service/fetch-json!
    ASSETS_ENDPOINT
    {:xform (fn [{:keys [assets assetTypes]}]
              {:f merge
               :args [{:assets (filter not-bootstrap-asset assets)
                       :asset-types (filter not-boostrap-asset-type assetTypes)}]})
     :on-error {:title "Asset Failure"
                :message "Unable to load assets and asset types due to
                          an unknown server error."}}))
