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

(ns sawtooth.http-test
  (:require [cljs.test :refer-macros [deftest are testing]]
            [sawtooth.http :refer [query-endpoint]]))


(deftest test-query-endpoint
  (are [x y] (= x y)
    "/url" (query-endpoint "/url" nil)
    "/url" (query-endpoint "/url" {})
    "/hello?x=1" (query-endpoint "/hello" {:x 1})
    "/foo?x=1&y=2" (query-endpoint "/foo" {:x 1 :y 2})
    "/bar?a=1" (query-endpoint "/bar" {:a 1 :b nil})
    "/bar" (query-endpoint "/bar" {:a nil})))
