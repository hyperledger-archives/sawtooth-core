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
(ns mktplace.components.format
  (:require [sawtooth.utils :refer [firstk]]))

(def object-name-pattern #"^/.+")

(defn valid-object-name? [s]
  (or (nil? s)
      (empty? s)
      (re-find object-name-pattern s)))

(defn object-name
  "Check if an object name is empty, and returns its id as needed"
  [{obj-id :id obj-name :name}]
  (if (or (nil? obj-name)
          (and (string? obj-name) (empty? obj-name)))
      obj-id
      obj-name))

(defn first-name
  "Finds the first item in the given collection wih the given id
  and returns its name.

  Params:

    coll - the search collection
    id - the id to find
    default-value - the value to return if none is found."
  [coll id default-value]
  (let [obj-name (firstk coll id :name)]
    (if (empty? obj-name)
        default-value
        obj-name)))

(defn asset-name-by-holding
  "Finds the asset name for the given holding"
  [assets {asset-id :asset}]
  (first-name assets asset-id "unknown"))

(defn asset-type-name-by-asset
  "Finds the asset-type name for a given asset"
  [asset-types {asset-type-id :asset-type}]
  (first-name asset-types asset-type-id "unknown"))

(defn participant-display-name
  "Returns the display name of a participant with the given id, from
  the given sequence of participants"
  [participants id]
  (first-name participants id "Unknown Participant"))
