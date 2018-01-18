/*
 Copyright 2017 Intel Corporation

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
------------------------------------------------------------------------------
*/

%module poet_enclave

%pythoncode %{
    import base64
    import hashlib
    import logging
    import os
    import json
    import time
    import toml

    from cryptography.hazmat import backends
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.exceptions import InvalidSignature

    from ssl import SSLError
    from requests.exceptions import Timeout
    from requests.exceptions import HTTPError

    from sawtooth_ias_client import ias_client

    from sawtooth_poet_common import sgx_structs
%}

%include <std_string.i>
%include <exception.i>

%exception  {
    try {
        $function
    } catch(MemoryError& e) {
        SWIG_exception(SWIG_MemoryError, e.what());
    } catch(IOError& e) {
        SWIG_exception(SWIG_IOError, e.what());
    } catch(RuntimeError& e) {
        SWIG_exception(SWIG_ValueError, e.what());
    } catch(IndexError& e) {
        SWIG_exception(SWIG_ValueError, e.what());
    } catch(TypeError& e) {
        SWIG_exception(SWIG_ValueError, e.what());
    } catch(DivisionByZero& e) {
        SWIG_exception(SWIG_DivisionByZero, e.what());
    } catch(OverflowError& e) {
        SWIG_exception(SWIG_OverflowError, e.what());
    } catch(SyntaxError& e) {
        SWIG_exception(SWIG_SyntaxError, e.what());
    } catch(ValueError& e) {
        SWIG_exception(SWIG_ValueError, e.what());
    } catch(SystemError& e) {
        SWIG_exception(SWIG_SystemError, e.what());
    } catch(SystemBusyError& e) {
        SWIG_exception(SWIG_SystemError, e.what());
    } catch(UnknownError& e) {
        SWIG_exception(SWIG_UnknownError, e.what());
    } catch(...) {
        SWIG_exception(SWIG_RuntimeError,"Unknown exception");
    }
}

%{
#include "common.h"
%}
%{
#include "poet_enclave.h"
%}

%include "poet_enclave.h"

%init %{
    InitializePoetEnclaveModule();
%}
%pythoncode %{

__IAS_REPORT_KEY = \
    b"-----BEGIN PUBLIC KEY-----\n" \
    b"MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqXot4OZuphR8nudFrAFi\n" \
    b"aGxxkgma/Es/BA+tbeCTUR106AL1ENcWA4FX3K+E9BBL0/7X5rj5nIgX/R/1ubhk\n" \
    b"KWw9gfqPG3KeAtIdcv/uTO1yXv50vqaPvE1CRChvzdS/ZEBqQ5oVvLTPZ3VEicQj\n" \
    b"lytKgN9cLnxbwtuvLUK7eyRPfJW/ksddOzP8VBBniolYnRCD2jrMRZ8nBM2ZWYwn\n" \
    b"XnwYeOAHV+W9tOhAImwRwKF/95yAsVwd21ryHMJBcGH70qLagZ7Ttyt++qO/6+KA\n" \
    b"XJuKwZqjRlEtSEz8gZQeFfVYgcwSfo96oSMAzVr7V0L6HSDLRnpb6xxmbPdqNol4\n" \
    b"tQIDAQAB\n" \
    b"-----END PUBLIC KEY-----"

_poet = None
_ias = None
logger = logging.getLogger(__name__)
_sig_rl_update_time = None
_sig_rl_update_period = 8*60*60 # in seconds every 8 hours
_epid_group = None

def update_sig_rl():
    global _epid_group
    global  _sig_rl_update_time
    global  _sig_rl_update_period
    if not _sig_rl_update_time \
        or (time.time() - _sig_rl_update_time) > _sig_rl_update_period:

        sig_rl = ""
        if(not _is_sgx_simulator()):
            if _epid_group is None:
                _epid_group = _poet.get_epid_group()
            sig_rl = _ias.get_signature_revocation_lists(_epid_group)
            logger.debug("Received SigRl of {} bytes ".format(len(sig_rl)))
        _poet.set_signature_revocation_list(sig_rl)
        _sig_rl_update_time = time.time()


def initialize(config_dir, data_dir):
    global _poet
    global _ias
    global logger

    _SetLogger(logger)

    config_file = os.path.join(config_dir, 'poet_enclave_sgx.toml')
    logger.info('Loading PoET enclave config from: %s', config_file)

    # Lack of a config file is a fatal error, so let the exception percolate
    # up to caller
    with open(config_file) as fd:
        toml_config = toml.loads(fd.read())

    # Verify the integrity (as best we can) of the TOML configuration file
    valid_keys = set(['spid', 'ias_url', 'spid_cert_file'])
    found_keys = set(toml_config.keys())

    invalid_keys = found_keys.difference(valid_keys)
    if invalid_keys:
        raise \
            ValueError(
                'PoET enclave config file contains the following invalid '
                'keys: {}'.format(
                    ', '.join(sorted(list(invalid_keys)))))

    missing_keys = valid_keys.difference(found_keys)
    if missing_keys:
        raise \
            ValueError(
                'PoET enclave config file missing the following keys: '
                '{}'.format(
                    ', '.join(sorted(list(missing_keys)))))

    if not _ias:
        _ias = \
            ias_client.IasClient(
                ias_url=toml_config['ias_url'],
                spid_cert_file=toml_config['spid_cert_file'])

    if not _poet:
        if os.name == 'nt':
            shared_library_ext = 'dll'
        else:
            shared_library_ext = 'so'
        enclave_file_name = \
            'libpoet-enclave.signed.{}'.format(shared_library_ext)

        sdir = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
        signed_enclave = os.path.join(sdir, enclave_file_name)
        if not os.path.exists(signed_enclave):
            signed_enclave = os.path.abspath(os.path.join(sdir, '..', '..', enclave_file_name))
        if not os.path.exists(signed_enclave):
            signed_enclave = os.path.join('/usr', 'lib', enclave_file_name)
        if not os.path.exists(signed_enclave):
            raise IOError("Could not find enclave shared object")

        logger.debug("Attempting to load enclave at: %s", signed_enclave)
        _poet = Poet(data_dir, signed_enclave, toml_config['spid'])

    sig_rl_updated = False
    while not sig_rl_updated:
        try:
            update_sig_rl()
            sig_rl_updated = True
        except (SSLError, Timeout, HTTPError) as e:
            logger.warning("Failed to retrieve initial sig rl from IAS: %s",
                str(e))
            logger.warning("Retrying in 60 sec")
            time.sleep(60)


def shutdown():
    global _poet
    global _ias
    global _sig_rl_update_time
    global _epid_group

    _poet = None
    _ias = None
    _sig_rl_update_time = None
    _epid_group = None

def _check_verification_report(verification_report, signature):
    # First thing we will do is verify the signature over the verification
    # report. The signature over the verification report uses RSA-SHA256.

    # Create a public key object based upon the known IAS report key
    public_key = \
        serialization.load_pem_public_key(
            __IAS_REPORT_KEY,
            backend=backends.default_backend())

    # Now verify the signature provided is valid for the verification
    # report received
    try:
        public_key.verify(
            base64.b64decode(signature),
            verification_report.encode(),
            padding.PKCS1v15(),
            hashes.SHA256())
    except InvalidSignature:
        raise ValueError('Verification report signature does not match')

    verification_report_dict = json.loads(verification_report)

    # Verify that the verification report meets the following criteria:
    # 1. Includes an ID field.

    if not 'id' in verification_report_dict:
        raise ValueError('AVR does not contain id field')

    # 2. Does not include a revocation reason.

    if 'revocationReason' in verification_report_dict:
        raise EnvironmentError('AVR indicates the EPID group has been revoked')

    # 3. Includes an enclave quote status

    isv_enclave_quote_status = \
        verification_report_dict.get('isvEnclaveQuoteStatus')
    if isv_enclave_quote_status is None:
        raise ValueError('AVR does not include an enclave quote status')

    # 4. Enclave quote status should be "OK".

    if isv_enclave_quote_status.upper() != 'OK':
        # Allow out of date severity issues to pass.
        if isv_enclave_quote_status.upper() == 'GROUP_OUT_OF_DATE':
            logger.error('Machine requires update (probably BIOS)'
                ' for SGX compliance.')
        else:
            raise EnvironmentError(
                'AVR enclave quote status is bad: {}'.format(
                    isv_enclave_quote_status))

    # 5. Includes an enclave quote.

    if not 'isvEnclaveQuoteBody' in verification_report_dict:
        raise ValueError('AVR does not contain quote body')

    # 6. Includes a PSE manifest status

    pse_manifest_status = \
        verification_report_dict.get('pseManifestStatus')
    if pse_manifest_status is None:
        raise ValueError('AVR does not include a PSE manifest status')

    # 7. PSE manifest status should be "OK".

    if pse_manifest_status.upper() != 'OK':
        # Allow out of date severity issues to pass.
        if pse_manifest_status.upper() == 'OUT_OF_DATE':
            logger.error('Machine requires update (probably BIOS)'
                ' for SGX compliance.')
        else:
            raise EnvironmentError(
                'AVR PSE manifest status is bad: {}'.format(
                    pse_manifest_status))

    # 8. Includes a PSE manifest hash.

    if not 'pseManifestHash' in verification_report_dict:
        raise ValueError('AVR does not contain PSE manifest hash')

    # 9. Includes an EPID psuedonym.

    if not 'epidPseudonym' in verification_report_dict:
        raise ValueError('AVR does not contain an EPID psuedonym')

    # 10. Includes a nonce

    if not 'nonce' in verification_report_dict:
        raise ValueError('AVR does not contain a nonce')

def get_enclave_measurement():
    global _poet
    return _poet.mr_enclave if _poet is not None else None

def get_enclave_basename():
    global _poet
    return _poet.basename if _poet is not None else None

def create_signup_info(originator_public_key_hash, nonce):
    # Part of what is returned with the signup data is an enclave quote, we
    # want to update the revocation list first.
    update_sig_rl()

    # Now, let the enclave create the signup data
    signup_data = _create_signup_data(originator_public_key_hash)
    if signup_data is None:
        return None

    # We don't really have any reason to call back down into the enclave
    # as we have everything we now need.  For other objects such as wait
    # timer and certificate they are serialized into JSON down in C++ code.
    #
    # Start building up the signup info dictionary we will serialize
    signup_info = {
        'poet_public_key': signup_data.poet_public_key,
        'proof_data': 'Not present',
        'anti_sybil_id': 'Not present'
    }

    # If we are not running in the simulator, we are going to go and get
    # an attestation verification report for our signup data.
    if not _is_sgx_simulator():
        response = \
            _ias.post_verify_attestation(
                quote=signup_data.enclave_quote,
                manifest=signup_data.pse_manifest,
                nonce=nonce)

        verification_report = response.get('verification_report')

        if verification_report is None:
            logger.warning('IAS response did not contain an AVR')
            return None

        signature = response.get('signature')
        if signature is None:
            logger.warning('IAS response did not contain an AVR signature')
            return None

        # Check the AVR to make sure it is valid and does not indicate
        # any errors
        try:
            _check_verification_report(verification_report, signature)
        except ValueError as e:
            logger.warning("Invalid attestation verification report",
                str(e))
            return None
        except EnvironmentError as e:
            logger.critical("Attestation errors prevent registering this"
                "validator, (Check SGX installation and/or BIOS level): %s",
                str(e))
            return None


        # Now put the proof data into the dictionary
        signup_info['proof_data'] = \
            json.dumps({
                'evidence_payload': {
                    'pse_manifest': signup_data.pse_manifest
                },
                'verification_report': verification_report,
                'signature': signature
            })

        # Grab the EPID psuedonym and put it in the anti-Sybil ID for the
        # signup info
        verification_report_dict = json.loads(verification_report)
        signup_info['anti_sybil_id'] = verification_report_dict.get('epidPseudonym')

    # Now we can finally serialize the signup info and create a corresponding
    # signup info object.  Because we don't want the sealed signup data in the
    # serialized version, we set it separately.

    signup_info_obj = deserialize_signup_info(json.dumps(signup_info))
    signup_info_obj.sealed_signup_data = signup_data.sealed_signup_data

    # Now we can return the real object
    return signup_info_obj


def create_wait_timer(sealed_signup_data,
                      validator_address,
                      previous_certificate_id,
                      local_mean):
                      
    return \
        _create_wait_timer(
            sealed_signup_data,
            validator_address,
            previous_certificate_id,
            local_mean)


def verify_wait_certificate(wait_certificate, poet_public_key):
    # Validate parameters
    if wait_certificate is None:
        raise ValueError("No wait certificate provided")
    if poet_public_key is None:
        raise ValueError("No PoET public key provided")
    if not isinstance(wait_certificate, WaitCertificate):
        raise TypeError("Wait certificate is not the correct type")
    if not isinstance(poet_public_key, str):
        raise TypeError("PoET public key is not the correct type")

    if _verify_wait_certificate(
            wait_certificate.serialized,
            wait_certificate.signature,
            poet_public_key):
        return True
    raise ValueError('Wait Certificate signature is invalid')

%}
