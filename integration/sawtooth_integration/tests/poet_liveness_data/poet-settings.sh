#!/bin/bash
settings=""
settings="$settings sawtooth.poet.target_wait_time=5"
settings="$settings sawtooth.poet.initial_wait_time=25"
settings="$settings sawtooth.publisher.max_batches_per_block=100"

echo "$settings"
