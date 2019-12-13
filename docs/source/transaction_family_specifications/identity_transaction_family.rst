***************************
Identity Transaction Family
***************************

Overview
=========
On-chain permissioning is desired for transactor key and validator key
permissioning. This feature requires that authorized participants for each
role be stored. Currently, the only form of identification on the network is
the entity's public key. Since lists of public keys are difficult to manage,
an identity namespace will be used to streamline managing identities.

The identity system described here is an extensible role and policy based
system for defining permissions in a way which can be utilized by other pieces
of the architecture. This includes the existing permissioning components for
transactor key and validator key, but in the future may also be used by
transaction family implementations.

The identity namespace:

- Encompasses ways to identify participants based on public keys
- Stores a set of permit and deny rules called "policies"
- Stores the roles that those policies apply to

Policies describe a set of identities that have permission to perform some
action, without specifying the logic of the action itself. Roles simply
reference a policy, providing a more flexible interface. For example, a policy
could be referenced by multiple roles. This way if the policy is updated, all
roles referencing the policy are updated as well. An example role might be named
"transactor", and references the policy that controls who is allowed to submit
batches and transactions on the network. This example is further described in
:doc:`Transactor Permissioning <../sysadmin_guide/configuring_permissions>`.

.. note::
  This transaction family will serve as a reference specification
  and implementation and may also be used in production. A custom implementation
  can be used so long as they adhere to the same addressing scheme and content
  format for policies and roles.


State
=====

Policies
--------
A policy will have a name and a list of entries. Each policy entry will have a
list of type/key pairs. The type will be either PERMIT_KEY or DENY_KEY.
Each key in a type/key pair will be a public key.

.. code-block:: protobuf

  // Policy will be stored in a PolicyList to account for hash collisions
  message PolicyList {
    repeated Policy policies = 1;
  }

  message Policy {

    enum EntryType {
      ENTRY_TYPE_UNSET = 0;
      PERMIT_KEY = 1;
      DENY_KEY = 2;
    }

    message Entry {
      // Whether this is a PERMIT_KEY or DENY_KEY entry
      EntryType type = 1;

      // This should a public key or * to refer to all participants.
      string key = 2;
    }

    // name of the policy, this should be unique.
    string name = 1;

    // list of Entries
    // The entries will be processed in order from first to last.
    repeated Entry entries = 2;
  }

Roles
-----
A role will be made up of a role name and the name of the policy to be enforced
for that role. The data will be stored in state at the address described above
using the following protobuf messages:

.. code-block:: protobuf

  // Roles will be stored in a RoleList to handle state collisions. The Roles
  // will be sorted by name.
  message RoleList {
    repeated Role roles = 1;
  }

  message Role{
    // Role name
    string name = 1;

    // Name of corresponding policy
    string policy_name = 2;
  }

Addressing
----------
All identity data will be stored under the special namespace of “00001d”.

For each policy, the address will be formed by concatenating the namespace, the
special policy namespace of “00”, and the first 62 characters of the SHA-256
hash of the policy name:

.. code-block:: pycon

 >>> "00001d" + "00" + hashlib.sha256(policy_name.encode()).hexdigest()[:62]

Address construction for roles will follow a pattern similar to address
construction in the settings namespace. Role names will be broken into four
parts, where parts of the string are delimited by the "." character. For
example, the key a.b.c would be split into the parts "a", "b", "c", and the
empty string. If a key would have more than four parts the extra parts are left
in the last part. For example, the key a.b.c.d.e would be split into "a", "b",
"c", and "d.e".

A short hash is computed for each part. For the first part the first 14
characters of the SHA-256 hash are used. For the remaining parts the first 16
characters of the SHA-256 hash are used. The address is formed by concatenating
the identity namespace “00001d”, the role namespace “01”, and the four short
hashes.

For example, the address for the role client.query_state would be constructed
as follows:

.. code-block:: pycon

  >>> "00001d"+ "01" + hashlib.sha256('client'.encode()).hexdigest()[:14]+ \
    hashlib.sha256('query_state'.encode()).hexdigest()[:16]+ \
    hashlib.sha256(''.encode()).hexdigest()[:16]+ \
    hashlib.sha256(''.encode()).hexdigest()[:16]

Transaction Payload
===================
Identity transaction family payloads are defined by the following protocol
buffers code:

File: sawtooth-core/families/identity/protos/identity.proto

.. code-block:: protobuf

  message IdentityPayload {
      enum IdentityType {
        POLICY = 0;
        ROLE = 1;
      }

      // Which type of payload this is for
      IdentityType type = 1;

      // Serialize bytes of a role or a policy
      bytes data = 2;
  }

Transaction Header
==================

Inputs and Outputs
------------------

The inputs for Identity family transactions must include:

* the address of the setting *sawtooth.identity.allowed_keys*
* the address of the role or policy being changed
* if setting a role, the address of the policy to assign to the role

The outputs for Identity family transactions must include:

* the address of the role or policy being changed

Dependencies
------------

None.

Family
------

- family_name: "sawtooth_identity"
- family_version: "1.0"

Execution
=========
Initially, the transaction processor gets the current values of
sawtooth.identity.allowed_keys from the state.

The public key of the transaction signer is checked against the values in the
list of allowed keys. If it is empty, no roles or policy can be updated. If
the transaction signer is not in the allowed keys the transaction is invalid.

Whether this is a role or a policy transaction is checked by looking at the
``IdentityType`` in the payload.

If the transaction is for setting a policy, the data in the payload will be
parsed to form a ``Policy`` object. The ``Policy`` object is then checked to
make sure it has a name and at least one entry. If either are missing, the
transaction is considered invalid. If the policy is determined to be whole, the
address for the new policy is fetched. If there is no data found at the address,
a new ``PolicyList`` object is created, the new policy is added, and the policy
list is applied to state. If there is data, it is parsed into a ``PolicyList``.
The new policy is added to the policy list, replacing any policy with the same
name, and the policy list is applied to state.

If the transaction is for setting a role, the data in the payload will be
parsed to form a ``Role`` object. The ``Role`` object is then checked to make
sure it has a name and a policy_name. If either are missing, the transaction is
considered invalid. The policy_name stored in the role must match a ``Policy``
already stored in state, if no policy is found stored at the address created
by the policy_name, the transaction is invalid. If the policy exist, the
address for the new role is fetched. If there is no data found at the address,
a new ``RoleList`` object is created, the new role is added, and the policy
list is applied to state. If there is data, it is parsed into a ``RoleList``.
The new role is added to the role list, replacing any role with the same name,
and the role list is applied to state.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
