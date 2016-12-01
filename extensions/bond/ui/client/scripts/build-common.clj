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

(require '[cljs.build.api :as build-api]
         '[figwheel-sidecar.cljs-utils.exception-parsing :as ex-parse]
         '[clojure.string :refer [join]]
         '[clojure.pprint :refer [pprint]]
         'cljs.analyzer)

(def escalated-warnings (atom []))
(def warnings (atom []))

(defn warning-escalator [warning-type env & [extra]]
  (when-let [warning (ex-parse/extract-warning-data warning-type env extra)]
    (if (warning-type #{:undeclared-var :undeclared-ns :undeclared-ns-form})
      (swap! escalated-warnings conj warning)
      (swap! warnings conj warning))))

(defn cljs-build [build-id]
  (println "Building CLJS config" build-id)
  (cljs.analyzer/with-warning-handlers [warning-escalator]
    (let [build-config (->> (read-string  (slurp "./scripts/cljs-build-config.edn"))
                            (filter #(= (name build-id) (:id %)))
                            (first))
          sources (apply cljs.build.api/inputs (:source-paths build-config))
          build-opts (:compiler build-config)]
      (try
        (build-api/build sources build-opts)
        (catch Exception e
          (ex-parse/print-exception e)
          (System/exit -2)))

      (doseq [warning @warnings]
        (-> warning
            ex-parse/format-warning
            println)
        (println))

      (doseq [warning @escalated-warnings]
        (-> warning
            ex-parse/parse-warning
            ex-parse/warning-data->display-data
            (assoc :error-type "Escalated Compiler Warning")
            ex-parse/formatted-exception-display-str
            println)
        (println))

      (System/exit (if (empty? @escalated-warnings) 0 -1)))))
