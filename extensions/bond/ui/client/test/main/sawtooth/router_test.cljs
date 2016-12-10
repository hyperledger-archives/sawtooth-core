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

(ns sawtooth.router-test
  (:require [cljs.test :refer-macros [deftest testing is async use-fixtures]]
            [sawtooth.router :as router]
            [secretary.core :as secretary :refer-macros [defroute]]
            [sawtooth.state])
  (:require-macros [sawtooth.test-common :refer [defer next-tick]]))


(use-fixtures :each {:after #(set! (.-hash js/window.location) "")})

(secretary/reset-routes!)

(defroute test1-path "/test1" [] :test1)

(defroute test2-path "/test2" [] :test2)

(deftest test-replace
  (async done
  (testing "Replacing a path"
    (let [history-count (.-length js/window.history)]
      (is (= :test2 (router/replace (test2-path))))

      (defer 100
        (is (= "#/test2" (.-hash js/window.location)))
        (is (= 0 (- (.-length js/window.history) history-count)))
        (done))))))
