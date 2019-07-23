**********************************************
Adding Authorized Users for Settings Proposals
**********************************************

Sawtooth supports on-chain settings to configure validator behavior, consensus,
permissions, and more. The Settings transaction processor (or an equivalent)
handles these on-chain settings.
The on-chain setting ``sawtooth.settings.vote.authorized_keys`` contains the
public keys of validators and users who are allowed to propose and vote on
settings changes.

By default, settings changes are restricted to the owner of the private key used
to create the genesis block, as specified by the ``--key privatekeyfile`` option
for the ``sawswet genesis`` command. The associated public key is stored in
``sawtooth.settings.vote.authorized_keys`` when the genesis block is created.

If the validator key was used to create the genesis block, we **strongly**
recommend adding one or more user keys to this setting. Otherwise, if the first
node becomes unavailable, no settings changes can be made.

This procedure describes how to add a user key to
``sawtooth.settings.vote.authorized_keys``.

1. Log into the Sawtooth node that has your private key file.

   .. important::

      If the genesis block was created with the first validator's key, and
      no user keys are authorized to change settings, you **must** run this
      procedure on the same node that created the genesis block. The
      ``sawset proposal create`` command requires the private validator key
      that was generated on that node.

#. Make sure that the Settings transaction processor (or an equivalent) and the
   REST API are running, as described in :doc:`systemd`.

#. Display the existing setting.

   .. code-block:: console

      $ sawtooth settings list sawtooth.settings.vote.authorized_keys

   The output will resemble this example:

   .. code-block:: console

      sawtooth.settings.vote.authorized_keys: 0276023d4f7323103db8d8683a4b7bc1eae1f66...

   If you want to add a key to the existing list, copy the key strings for the
   next step.

#. Add the new user's public key to the list of those allowed to change
   settings.

   .. code-block:: none

     $ sawset proposal create --key {PRIVATE-KEY} \
     sawtooth.settings.vote.authorized_keys='{OLDLIST},{NEWKEY}'

   .. note::

      * For ``{PRIVATE-KEY}``, specify the path to your private key file (or the
        validator's private key file, if it was used to create the genesis
        block).

      * For ``{OLDLIST}``, use the list of existing keys from step 2.
        To delete a key, omit it from this list.

      * For ``{NEWKEY}``, use the public key of the user you want to add.

#. To see the changed setting, run ``sawtooth settings list`` again.

   .. code-block:: console

      $ sawtooth settings list sawtooth.settings.vote.authorized_keys

   Check that the new user key appears on the list.

**About proposal voting**

Each settings change must receive a certain amount of votes in order to be
accepted. By default, only one vote is required, and the settings proposal
contains an automatic "yes" vote from the user (or validator) who submitted
the proposal. For information on configuring more complex voting schemes,
see :doc:`/transaction_family_specifications/settings_transaction_family`.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
