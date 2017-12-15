/**
 * Copyright 2017 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

#include "c11_support.h"

#include <string.h>

#include <openssl/bio.h>
#include <openssl/evp.h>
#include <openssl/err.h>
#include <openssl/pem.h>
#include <openssl/engine.h>
#include <openssl/conf.h>

// Extract the private and public keys from the PEM file, using the supplied
// password to decrypt the file if encrypted. priv_key and pub_key must point to
// an array o at least 65 and 131 character respectively.
int load_pem_key(char *pemstr, size_t pemstr_len, char *password,
                 char *out_priv_key, char *out_pub_key) {

  BIO *in = NULL;

  BN_CTX *ctx = NULL;
  const EC_GROUP *group;
  EC_KEY *eckey = NULL;
  const EC_POINT *pub_key_point = NULL;
  const BIGNUM *priv_key = NULL, *pub_key = NULL;

  char *priv_key_hex = NULL;
  char *pub_key_hex = NULL;

  in = BIO_new_mem_buf(pemstr, (int)pemstr_len);

  // Read key from stream, decrypting with password if not NULL
  if (password != NULL && strcmp("", password) != 0) {
    // Initialize ciphers
    ERR_load_crypto_strings ();
    OpenSSL_add_all_algorithms ();

    eckey = PEM_read_bio_ECPrivateKey(in, NULL, NULL, password);
    if (eckey == NULL) {
      return -1; // Failed to decrypt or decode private key
    }
  } else {
    if ((eckey = PEM_read_bio_ECPrivateKey(in, NULL, NULL, NULL)) == NULL) {
      return -1; // Failed to decode private key
    }
  }
  BIO_free(in);

  // Deconstruct key into big numbers
  if ((ctx = BN_CTX_new()) == NULL) {
    return -2; // Failed to create new big number context
  }
  if ((group = EC_KEY_get0_group(eckey)) == NULL) {
    return -3; // Failed to load group
  }
  if ((priv_key = EC_KEY_get0_private_key(eckey)) == NULL) {
    return -4; // Failed to load private key
  }
  if ((pub_key_point = EC_KEY_get0_public_key(eckey)) == NULL) {
    return -5; // Failed to load public key point
  }
  pub_key = EC_POINT_point2bn(group, pub_key_point, EC_KEY_get_conv_form(eckey), NULL, ctx);
  if (pub_key == NULL) {
    return -6; // Failed to construct public key from point
  }

  priv_key_hex = BN_bn2hex(priv_key);
  pub_key_hex = BN_bn2hex(pub_key);
  strncpy_s(out_priv_key, 64 + 1, priv_key_hex, 64 + 1);
  strncpy_s(out_pub_key, 130 + 1, pub_key_hex, 130 + 1);
  OPENSSL_free(priv_key_hex);
  OPENSSL_free(pub_key_hex);
  return 0;
}
