# Copyright 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# ------------------------------------------------------------------------------

The file simulator_rk_pub.pem contains the public key that is used by the
validator registry transaction processor when verifying the signatures of the
attestation verification report included in the validator's signup information.

When using the PoET simulator, the contents of this file must be used to set the value sawtooth.poet.report_public_key_pem in the configuration settings on the blockchain before the first validator registry transaction is submitted.
