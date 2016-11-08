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
(ns mktplace.components.portfolio-test
  (:require [cljs.test :refer-macros [deftest testing is async]]
            [om.core :as om]
            [mktplace.components.portfolio :as portfolio]
            [sawtooth.test-common
             :as tcomm
             :refer-macros [with-container]]))

(def asset-types [{:id "12345"
                   :name "asset-type1"}
                  {:id "98765"
                   :name "asset-type2"}])

(defn- text-in [parent cssClass]
  (-> (tcomm/first-element-by {:cssClass cssClass :container parent})
      (tcomm/text)))

(defn- list-rows [parent list-id]
  (-> (tcomm/first-element parent list-id)
      (tcomm/children)))

(defn mount-portfolio-in
  ([container asset-types assets holdings] (mount-portfolio-in container asset-types assets holdings nil))
  ([container asset-types assets holdings selections]
   (om/root portfolio/portfolio
            {:assets assets
             :asset-types asset-types
             :selections selections
             :holdings holdings}
            {:target container})))

(deftest test-empty-portfolio
  (with-container c
    (mount-portfolio-in c asset-types [] [])

    (let [asset-rows (list-rows c :#assets)]
      (is (= 1 (count asset-rows)))
      (is (= "No Assets" (tcomm/text (first asset-rows)))))

    (let [holding-rows (list-rows c :#holdings)]
      (is (= 1 (count holding-rows)))
      (is (= "No Holdings" (tcomm/text (first holding-rows)))))))

(deftest test-portfolio-no-holdings
  (with-container c
    (mount-portfolio-in c
      asset-types
      [{:id "a1"
        :asset-type "12345"
        :name "/asset/type1/a1"
        :description "First asset"}
       {:id "a2"
        :asset-type "12345"
        :name "/asset/type1/a2"
        :description "Second asset"}]
      [])

    (let [asset-rows (list-rows c :#assets)]
      (is (= 2 (count asset-rows)))
      (let [first-row (first asset-rows)]
        (is (= "/asset/type1/a1" (text-in first-row "asset-name")))
        (is (= "asset-type1" (text-in first-row "asset-type"))))
      (let [second-row (second asset-rows)]
        (is (= "/asset/type1/a2" (text-in second-row "asset-name")))
        (is (= "asset-type1" (text-in second-row "asset-type"))))
      )

    (let [holding-rows (list-rows c :#holdings)]
      (is (= 1 (count holding-rows)))
      (is (= "Select an Asset to see Holdings" (tcomm/text (first holding-rows)))))))

(deftest test-selected-asset
  (let [assets [{:id "a1"
                 :asset-type "12345"
                 :name "/asset/type1/a1"
                 :description "First asset"}
                {:id "a2"
                 :asset-type "12345"
                 :name "/asset/type1/a2"
                 :description "Second asset"}]]
  (with-container c
    (mount-portfolio-in c
      asset-types
      assets
      []
      {:asset (first assets)})

    (let [asset-rows (list-rows c :#assets)]
      (is (contains? (tcomm/classes (first asset-rows)) "active"))))))

(deftest test-load-portfolio
  (with-container c
    (mount-portfolio-in c
      asset-types
      [{:id "a1"
        :asset-type "12345"
        :name "/asset/type/a1"
        :description "First asset"}
       {:id "a2"
        :asset-type "98765"
        :name "/asset/type/a2"
        :description "Second asset"}]
      [{:id "1"
        :asset "a1"
        :name "/holding/type1/name1"
        :count 50}
       {:id "2"
        :asset "a2"
        :name "/holding/type2/name2"
        :count 51}])

    (let [holding-rows (list-rows c :#holdings)]
      (is (= 2 (count holding-rows)))
      ; The should be sorted by count
      (let [first-row (first holding-rows)]
        (is (= "/holding/type2/name2" (text-in first-row "holding-name")))
        (is (= "/asset/type/a2" (text-in first-row "holding-type")))
        (is (= "51" (text-in first-row "holding-count"))))
      (let [second-row (second holding-rows)]
        (is (= "/holding/type1/name1" (text-in second-row "holding-name")))
        (is (= "/asset/type/a1" (text-in second-row "holding-type")))
        (is (= "50" (text-in second-row "holding-count")))))))

(deftest test-selected-holding
  (let [holdings [{:id "1"
                   :asset "a1"
                   :name "/holding/type1/name1"
                   :count 50}
                  {:id "2"
                   :asset "a2"
                   :name "/holding/type2/name2"
                   :count 51}]]
    (with-container c
      (mount-portfolio-in c
        asset-types
        [{:id "a1"
          :asset-type "12345"
          :name "/asset/type/a1"
          :description "First asset"}
         {:id "a2"
          :asset-type "98765"
          :name "/asset/type/a2"
          :description "Second asset"}]
        holdings
        {:holding (first holdings)})

      (let [holding-rows (list-rows c :#holdings)]
        (is (contains? (tcomm/classes (second holding-rows)) "active"))))))
