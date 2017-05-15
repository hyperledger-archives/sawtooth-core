import time
import hashlib
import requests
import sys

import yaml

import sawtooth_signing as signing

import sawtooth_sdk.protobuf.evm_pb2 as evm_pb2
import sawtooth_sdk.protobuf.transaction_pb2 as transaction_pb2
import sawtooth_sdk.protobuf.batch_pb2 as batch_pb2

def sha(d):
    if isinstance(d, str):
        d=d.encode('utf-8')
    return hashlib.sha512(d).hexdigest()

if len(sys.argv) > 1:
    with open(sys.argv[1]) as fin:
        payloadDict = yaml.safe_load(fin.read())
else:
    print("Please specify YAML to load")
    exit(1)

private_key = signing.generate_privkey()
public_key = signing.generate_pubkey(private_key)

namespace = sha('burrow-evm')[0:6]
print(namespace)

# Payload
payload = evm_pb2.EvmPayload()
if 'caller' in payloadDict:
    payload.caller=payloadDict['caller']
if 'callee' in payloadDict:
    payload.callee=payloadDict['callee']
if 'code' in payloadDict:
    payload.code=bytes.fromhex(payloadDict['code'])
if 'input' in payloadDict:
    payload.input=bytes.fromhex(payloadDict['input'])
if 'value' in payloadDict:
    payload.value=payloadDict['value']
if 'gas' in payloadDict:
    payload.gas=payloadDict['gas']
print(payload)

payloadData = payload.SerializeToString()
payloadHash = sha(payloadData)

# Transaction
header = transaction_pb2.TransactionHeader(
    signer_pubkey=public_key,
    family_name='burrow-evm',
    family_version='1.0',
    inputs=[namespace],
    outputs=[namespace],
    dependencies=[],
    payload_encoding="application/protobuf",
    payload_sha512=payloadHash,
    batcher_pubkey=public_key,
    nonce=time.time().hex().encode())
print(header)
headerData = header.SerializeToString()
headerSig = signing.sign(headerData, private_key)

txn = transaction_pb2.Transaction(
    header=headerData,
    payload=payloadData,
    header_signature=headerSig,
)
print(txn)

# Batch
batchHeader = batch_pb2.BatchHeader(
    signer_pubkey=public_key,
    transaction_ids=[headerSig]
)
print(batchHeader)
batchHeaderData = batchHeader.SerializeToString()
batchHeaderSig = signing.sign(batchHeaderData, private_key)

batch = batch_pb2.Batch(
    header=batchHeaderData,
    transactions=[txn],
    header_signature=batchHeaderSig,
)
print(batch)

# BatchList

batchList = batch_pb2.BatchList(batches=[batch])
batchListData = batchList.SerializeToString()

resp = requests.post("http://localhost:8080/batches", batchListData, headers={
    'Content-Type': 'application/octet-stream',
    'Content-Length': str(len(batchListData))
})

print(resp.status_code)
print(resp.text)
