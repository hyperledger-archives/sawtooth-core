# Copyright 2018-2020 Cargill Incorporated
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


crates := '\
    libsawtooth \
    validator \
    adm \
    perf/sawtooth_perf \
    perf/smallbank_workload \
    perf/intkey_workload \
    perf/sawtooth_workload \
    families/settings/sawtooth_settings \
    families/identity/sawtooth_identity \
    families/battleship \
    families/block_info/sawtooth_block_info \
    families/smallbank/smallbank_rust \
    '

features := '\
    --features=experimental \
    --features=stable \
    --features=default \
    --no-default-features \
    '

docker-build-doc:
    docker build . -f ci/sawtooth-build-docs -t sawtooth-build-docs
    docker run --rm -v $(pwd):/project/sawtooth-core sawtooth-build-docs

build:
    #!/usr/bin/env sh
    set -e
    for feature in $(echo {{features}})
    do
        for crate in $(echo {{crates}})
        do
            cmd="cargo build --tests --manifest-path=$crate/Cargo.toml $feature"
            echo "\033[1m$cmd\033[0m"
            $cmd
        done
    done
    echo "\n\033[92mBuild Success\033[0m\n"

clean:
    #!/usr/bin/env sh
    set -e
    for crate in $(echo {{crates}})
    do
        cmd="cargo clean --manifest-path=$crate/Cargo.toml"
        echo "\033[1m$cmd\033[0m"
        $cmd
        cmd="rm -f $crate/Cargo.lock"
        echo "\033[1m$cmd\033[0m"
        $cmd
    done

fix:
    #!/usr/bin/env sh
    set -e
    for crate in $(echo {{crates}})
    do
        for feature in $(echo {{features}})
        do
            cmd="cargo fix --manifest-path=$crate/Cargo.toml $feature"
            echo "\033[1m$cmd\033[0m"
            $cmd
        done
    done
    echo "\n\033[92mFix Success\033[0m\n"

lint:
    #!/usr/bin/env sh
    set -e
    for crate in $(echo {{crates}})
    do
        cmd="cargo fmt --manifest-path=$crate/Cargo.toml -- --check"
        echo "\033[1m$cmd\033[0m"
        $cmd
    done
    for crate in $(echo {{crates}})
    do
        for feature in $(echo {{features}})
        do
            cmd="cargo clippy --manifest-path=$crate/Cargo.toml $feature -- -D warnings"
            echo "\033[1m$cmd\033[0m"
            $cmd
        done
    done
    echo "\n\033[92mLint Success\033[0m\n"


docker-lint:
    docker-compose -f docker/compose/run-lint.yaml up \
        --build \
        --abort-on-container-exit \
        --exit-code-from lint-python \
        lint-python

test:
    #!/usr/bin/env sh
    set -e
    for feature in $(echo {{features}})
    do
        for crate in $(echo {{crates}})
        do
            cmd="cargo build --tests --manifest-path=$crate/Cargo.toml $feature"
            echo "\033[1m$cmd\033[0m"
            $cmd
            cmd="cd $crate && cargo test $feature"
            echo "\033[1m$cmd\033[0m"
            (eval $cmd)
        done
    done
    echo "\n\033[92mTest Success\033[0m\n"
