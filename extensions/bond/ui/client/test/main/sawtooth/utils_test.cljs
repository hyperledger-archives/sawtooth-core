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

(ns sawtooth.utils-test
  (:require [cljs.test :refer-macros [deftest testing are is async use-fixtures]]
            [sawtooth.utils :as utils]))


(deftest test-index-of
  (are [x y] (= x y)
       0 (utils/index-of 1 [1 2 3])
       1 (utils/index-of 2 [1 2 3])
       2 (utils/index-of 3 [1 2 3])
       nil (utils/index-of 4 [1 2 3])))

(deftest test-index-of-with-pred
  (let [c [{:id 10} {:id 12} {:id 15}]]
    (are [x y] (= x y)
         0 (utils/index-of #(= 10 (:id %)) c)
         1 (utils/index-of #(= 12 (:id %)) c)
         2 (utils/index-of #(= 15 (:id %)) c)
         nil (utils/index-of :foo c))))

(deftest test-firstk
  (let [c [{:id 1 :name "one"} {:id 2 :name "two"} {:not-id "something" :foo "bar"} {:id "3"}]]
    (are [x y] (= x y)
         "one" (utils/firstk c 1 :name)
         "two" (utils/firstk c 2 :name)
         nil (utils/firstk c 4 :name)
         nil (utils/firstk c "3" :name)

         "bar" (utils/firstk c :not-id "something" :foo)
         nil (utils/firstk c :not-id "something" :bar)
         nil (utils/firstk c :not-id "nothing" :foo))))

(deftest test-without-nil
  (are [x y] (= x y)
       {:x 1 :y 2} (utils/without-nil {:x 1 :y 2})
       {:x 1} (utils/without-nil {:x 1 :y nil})
       {:x {:a 1}} (utils/without-nil {:x {:a 1 :b nil}})
       {} (utils/without-nil {:x nil :y nil})
       {} (utils/without-nil {})
       nil (utils/without-nil nil)))
