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

(require
 '[figwheel-sidecar.repl-api :as ra]
 '[com.stuartsierra.component :as component])

(import 'java.lang.Runtime)

(def with-polling? (= (System/getenv "ENABLE_FILE_POLLING") "true"))

(when with-polling?
  (println "Enabling file polling..."))

(def figwheel-config
  {:figwheel-options (merge {:css-dirs ["resources/public/css"]}
                      (if with-polling? {:hawk-options {:watcher :polling}} {}))
   :build-ids ["dev" "test"]
   :all-builds (read-string (slurp "scripts/cljs-build-config.edn"))})

(def sass-config
  {:executable-path "sass" ; e.g. /usr/local/bin/sass
   :input-dir "src-style" ; location of the sass/scss files
   :output-dir "resources/public/css"})

(defrecord Figwheel []
  component/Lifecycle
  (start [config]
    (ra/start-figwheel! config)
    config)
  (stop [config]
    (ra/stop-figwheel!)
    config))

(defrecord SassWatcher [executable-path input-dir output-dir]
  component/Lifecycle
  (start [config]
    (if (not (:sass-watcher-process config))
      (do
        (println "Figwheel: Starting SASS watch process")
        (assoc config :sass-watcher-process
               (.exec (Runtime/getRuntime)
                      (str executable-path " --watch " input-dir ":" output-dir))))
      config))
  (stop [config]
    (when-let [process (:sass-watcher-process config)]
      (println "Figwheel: Stopping SASS watch process")
      (.destroy process))
    config))

(def system
  (atom
   (component/system-map
    :figwheel (map->Figwheel figwheel-config)
    :sass (map->SassWatcher sass-config))))

(defn start []
  (swap! system component/start))

(defn stop []
  (swap! system component/stop))

(defn reload []
  (stop)
  (start))

(defn repl []
  (ra/cljs-repl))

;; Start the components and the repl
(start)
(repl)
