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

#pragma once

#include "shared_library.h"
#include <stdlib.h>

#ifdef LIBPOET_BUILD
    #define POET_FUNC   SHARED_LIBRARY_EXPORT
#else
    #define POET_FUNC   SHARED_LIBRARY_IMPORT
#endif // LIBPOET_BUILD

#ifdef __cplusplus
extern "C" {
#endif // _cplusplus

    typedef enum {
        POET_SUCCESS=0,
        POET_ERR_UNKNOWN=-1,
        POET_ERR_MEMORY=-2,
        POET_ERR_IO =-3,
        POET_ERR_RUNTIME=-4,
        POET_ERR_INDEX=-5,
        POET_ERR_DIVIDE_BY_ZERO=-6,
        POET_ERR_OVERFLOW =-7,
        POET_ERR_VALUE =-8,
        POET_ERR_SYSTEM =-9,
        POET_ERR_SYSTEM_BUSY =-10   /*
                                        Indicates that the system is busy and
                                        the operation may be retried again.  If
                                        retries fail this should be converted to
                                        a POET_ERR_SYSTEM for reporting.
                                    */
    } poet_err_t;

    typedef enum {
        POET_LOG_DEBUG = 0,
        POET_LOG_INFO = 1,
        POET_LOG_WARNING = 2,
        POET_LOG_ERROR = 3,
        POET_LOG_CRITICAL = 4,
    } poet_log_level_t;

    typedef void (*poet_log_t)(
        poet_log_level_t,
        const char* message
        );

    #define POET_IDENTIFIER_LENGTH 16

    /*
        Tests if libpoet is built against the SGX simulator or the SGX runtime
    */
    POET_FUNC int Poet_IsSgxSimulator();

    /*
        Returns the string associated with the last PoET error message.

        outMessage - A pointer to a buffer that, if not NULL, will upon return
            contain the message associated with the error code returned.
        inMessageLength - The size of the buffer pointed to by outMessage.
    */
    POET_FUNC poet_err_t Poet_GetLastErrorMessage(
        char* outMessage,
        size_t inMessageLength
        );

    /*
        Start the poet services

        inDataDirectory - A pointer to a string that contains the data
            directory for the validator.
        inPathToEnclave - A pointer to a string that contains the path to the
            enclave DLL.
        inSpid - A pointer to a string that contains the hex encoded SPID.
        logFunction - A pointer to the PoET log function.
    */
    POET_FUNC poet_err_t Poet_Initialize(
        const char* inDataDirectory,
        const char* inPathToEnclave,
        const char* inSpid,
        poet_log_t logFunction
        );

    /*
        Stop the poet services
    */
    POET_FUNC poet_err_t Poet_Terminate();

    /*
        Helper functions to determine buffer sizes for outgoing buffers filled
        in by enclave.
    */
    POET_FUNC size_t Poet_GetEpidGroupSize();
    POET_FUNC size_t Poet_GetEnclaveMeasurementSize();
    POET_FUNC size_t Poet_GetEnclaveBasenameSize();
    POET_FUNC size_t Poet_GetEnclavePseManifestHashSize();
    POET_FUNC size_t Poet_GetWaitTimerSize();
    POET_FUNC size_t Poet_GetWaitCertificateSize();
    POET_FUNC size_t Poet_GetSignatureSize();
    POET_FUNC size_t Poet_GetPublicKeySize();
    POET_FUNC size_t Poet_GetPseManifestSize();
    POET_FUNC size_t Poet_GetEnclaveQuoteSize();
    POET_FUNC size_t Poet_GetSealedSignupDataSize();

    /*
        Returns the EPID group as a Hex(base 16) encoded string.

        outEpidGroup - A pointer to a buffer that upon return will contain the
            hex encoded EPID group.
        inEpidGroupLength - The size of the buffer pointed to by outEpidGroup.
            The value to provide for this parameter may be obtained by calling
            Poet_GetEpidGroupSize().
    */
    POET_FUNC poet_err_t Poet_GetEpidGroup(
        char* outEpidGroup,
        size_t inEpidGroupLength
        );

    /*
        Returns characteristics about the enclave that can be used later when
        verifying signup information from other validators,

        outMrEnclave - A pointer to a buffer that upon return will contain the
            hex encoded enclave hash (aka, mr_enclave).
        inMrEnclaveLength - The size of the buffer pointed to by outMrEnclave.
            The value to provide for this parameter may be obtained by calling
            Poet_GetEnclaveMeasurementSize().
        outEnclaveBasename - A pointer to a buffer that upon return will contain
            the hex encoded enclave basename.
        inEnclaveBasenameLength - The size of the buffer pointed to by
            outEnclaveBasename.  The value to provide for this parameter may
            be obtained by calling Poet_GetEnclaveBasenameSize().
        outEnclavePseManifestHash - A pointer to a buffer that upon return will
            contain the hex encoded PSE manifest hash.
        inEnclavePseManifestHashSize - The size of the buffer pointed to by
            outEnclavePseManifest.  The value to provide for this parameter
            may be obtained by calling Poet_GetEnclavePseManifestHashSize().
    */
    POET_FUNC poet_err_t Poet_GetEnclaveCharacteristics(
        char* outMrEnclave,
        size_t inMrEnclaveLength,
        char* outEnclaveBasename,
        size_t inEnclaveBasenameLength,
        char* outEnclavePseManifestHash,
        size_t inEnclavePseManifestHashSize
        );

    /*
        takes in the results from the IAS server and
        stores the revocation list for future processing

        inSignatureRevocationList - A string containing the signature
            revocation list obtained from IAS.
    */
    POET_FUNC poet_err_t Poet_SetSignatureRevocationList(
        const char* inSignatureRevocationList
        );

    /*
        Generate the signup data and a linkable quote that can be used to create the
        IAS attestation verification report (AVR).

        inOriginatorPublicKeyHash - A string representing the SHA256 hash of the
            originator's public key.
        outPoetPublicKey - A pointer to a buffer that upon return will contain
            the hex encoded PoET public key generated.
        inPoetPublicKeySize - The size of the buffer pointed to by
            outPoetPublicKey.  The value to provide for this parameter may be
            obtained by calling Poet_GetPublicKeySize().
        outPseManifest - A pointer to a buffer that upon return will contain
            the base 64 encoded PSE manifest.
        inPseManifestSize - The size of the buffer pointed to by
            inPseManifestSize.  The value to provide for this parameter may be
            obtained by calling Poet_GetEnclavePseManifestSize().
        outEnclaveQuote - A pointer to a buffer that upon return will contain
            the base 64 encoded linkable enclave quote.
        inEnclaveQuoteSize - The size of the buffer pointed to by
            outEnclaveQuote.  The value to provide for this parameter may be
            obtained by calling Poet_GetEnclaveQuoteSize().
        outSealedSignupData - A pointer to a buffer that upon return will
            contain the base 64 encoded sealed signup data.
        inSealedSignupDataSize - The size of the buffer pointed to by
            outSealedSignupData.  The value to provide for this parameter may
            be obtained by calling Poet_GetSealedSignupDataSize().
    */
    POET_FUNC poet_err_t Poet_CreateSignupData(
        const char* inOriginatorPublicKeyHash,
        char* outPoetPublicKey,
        size_t inPoetPublicKeySize,
        char* outPseManifest,
        size_t inPseManifestSize,
        char* outEnclaveQuote,
        size_t inEnclaveQuoteSize,
        char* outSealedSignupData,
        size_t inSealedSignupDataSize
        );

    /*
        Use previously sealed signup data to re-establish the PoET enclave.

        inSealedSignupData - A string representing the base 64 encoded sealed
            signup data returned from a successful call to
            PoET_CreateSignupData.
        outPoetPublicKey - A pointer to a buffer that upon return will contain
            the hex encoded PoET public key contained within the sealed
            signup data.
        inPoetPublicKeySize - The size of the buffer pointed to by
            outPoetPublicKey.  The value to provide for this parameter may be
            obtained by calling Poet_GetPublicKeySize().
    */
    POET_FUNC poet_err_t Poet_UnsealSignupData(
        const char* inSealedSignupData,
        char* outPoetPublicKey,
        size_t inPoetPublicKeySize
        );

    /*
        Release the hardware counter used by signup data.

        inSealedSignupData - A string representing the base 64 encoded sealed
            signup data returned from a successful call to
            PoET_CreateSignupData.
    */
    POET_FUNC poet_err_t Poet_ReleaseSignupData(
        const char* inSealedSignupData
        );

    /*
        Verifies that the signup information provided is valid (as least as far
        as this enclave is concerned).

        inOriginatorPublicKeyHash - A string representing the SHA256 hash of the
            originator's public key.
        inPoetPublicKey - A string representing the hex encoding of the PoET
            public key created for the validator.
        inEnclaveQuote - A string representing the base 64 encoding of the
            enclave quote that the other validator provided to IAS when it
            created its signup information.
        inPseManifestHash - A string representing the hex encoding of the PSE
            manifest hash.
    */
    POET_FUNC poet_err_t Poet_VerifySignupInfo(
        const char* inOriginatorPublicKeyHash,
        const char* inPoetPublicKey,
        const char* inEnclaveQuote,
        const char* inPseManifestHash
        );

    /*
        Generates a wait timer that later, upon expiration, can be used to
        create a wait certificate.

        inSealedSignupData - A string representing the base 64 encoded sealed
            signup data returned from a successful call to
            PoET_CreateSignupData.
        inValidatorAddress - A string representing the validator address.
        inPreviousCertificateId - A string representing the ID of the previous
            wait certificate (i.e., the wait certificate from the block that
            has been most-recently added to the block chain).
        inRequestTime - The time wait timer was requested.
        inLocalMean - The local mean wait time that has been calculated.
        outSerializedWaitTimer - A pointer to a buffer that upon return will
            contain the serialized wait timer.
        inSerializedWaitTimerLength - The size of the buffer pointed to by
            outSerializedWaitTimer.  The value to provide for this parameter
            may be obtained by calling Poet_GetWaitTimerSize().
        outWaitTimerSignature - A pointer to a buffer that upon return will
            contain the base 64 encoded ECDSA signature over the serialized
            wait timer using the PoET secret key from the validator's signup
            info.
        inSerializedWaitTimerLength - The size of the buffer pointed to by
            outWaitTimerSignature.  The value to provide for this parameter may
            be obtained by calling Poet_GetSignatureSize().
    */
    POET_FUNC poet_err_t Poet_CreateWaitTimer(
        const char* inSealedSignupData,
        const char* inValidatorAddress,
        const char* inPreviousCertificateId,
        double inRequestTime,
        double inLocalMean,
        char* outSerializedWaitTimer,
        size_t inSerializedTimerLength,
        char* outWaitTimerSignature,
        size_t inWaitTimerSignatureLength
        );

    /*
        Generate the Wait Certificate.  If the wait timer has not expired or
        its signature is invalid, this will fail.

        inSerializedWaitTimer - A string representing a serialized wait timer
            created by a previously-successful call to PoET_CreateWaitTimer().
        inWaitTimerSignature - A string that contains the base 64 encoded ECDSA
            signature over the serialized wait timer (inSerializedWaitTimer)
            using the PoET secret key from the validator's signup info.  This
            was returned from a successful call to Poet_CreateWaitTimer().
        inBlockHash - A string representing the hash over the contents of the
            block for which this certificate is being created.
        outSerializedWaitCertificate - A pointer to a buffer that upon return
            will contain the serialized wait certificate.
        inSerializedWaitCertificateLength - The size of the buffer pointed to by
            outSerializedWaitCertificate.  The value to provide for this
            parameter may be obtained by calling Poet_GetWaitCertificateSize().
        outWaitCertificateSignature - A pointer to a buffer that upon return
            will contain the base 64 encoded ECDSA signature over the serialized
            wait certificate using the PoET secret key from the validator's
            signup info.
        inWaitCertificateSignatureLength - The size of the buffer pointed to by
            outWaitCertificateSignature.  The value to provide for this
            parameter may be obtained by calling Poet_GetSignatureSize().
    */
    POET_FUNC poet_err_t Poet_CreateWaitCertificate(
        const char* inSealedSignupData,
        const char* inSerializedWaitTimer,
        const char* inWaitTimerSignature,
        const char* inBlockHash,
        char* outSerializedWaitCertificate,
        size_t inSerializedWaitCertificateLength,
        char* outWaitCertificateSignature,
        size_t inWaitCertificateSignatureLength
        );

    /*
        Verifies that a wait certificate is valid.

        inSerializedWaitCertificate - A string representing a serialized wait
            certificate that was created by a previously-successful call to
            PoET_CreateWaitCertificate().
        inWaitCertificateSignature - A string that contains the base 64 encoded
            ECDSA signature over the serialized wait certificate
            (inSerializedWaitCertificate) using the PoET secret key created when
            the validator created its signup info.  This was returned from a
            successful call to Poet_CreateWaitCertificate().
        inPoetPublicKey - A string representing the encoded PoET public key used
            to verify the wait certificate signature.
    */
    POET_FUNC poet_err_t Poet_VerifyWaitCertificate(
        const char* inSerializedWaitCertificate,
        const char* inWaitCertificateSignature,
        const char* inPoetPublicKey
        );

#ifdef __cplusplus
};
#endif // _cplusplus
