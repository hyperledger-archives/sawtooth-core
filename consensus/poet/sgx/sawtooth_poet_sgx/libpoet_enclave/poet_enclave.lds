# Copyright 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# ------------------------------------------------------------------------------

enclave.so
{
    global:
        g_global_data_sim;
        g_global_data;
        enclave_entry;
        g_peak_heap_used;
    local:
        *;
};
