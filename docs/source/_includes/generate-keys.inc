.. important::

   For PBFT, repeat this procedure on the other nodes in the initial network.
   When you create the genesis block on the first node, you will need the
   validator keys for at least three other nodes.

1. Generate your user key for Sawtooth.

   .. code-block:: console

      $ sawtooth keygen my_key
      writing file: /home/yourname/.sawtooth/keys/my_key.priv
      writing file: /home/yourname/.sawtooth/keys/my_key.pub

   .. note::

      This command specifies ``my_key`` as the base name for the key files,
      to be consistent with the key name that is used in some example Docker and
      Kubernetes files. By default (when no key name is specified), the
      ``sawtooth keygen`` command uses your user name.

#. Generate the key for the validator, which runs as root.

   .. code-block:: console

       $ sudo sawadm keygen
       writing file: /etc/sawtooth/keys/validator.priv
       writing file: /etc/sawtooth/keys/validator.pub

   .. note::

      By default, this command stores the validator key files in
      ``/etc/sawtooth/keys/validator.priv`` and
      ``/etc/sawtooth/keys/validator.pub``.
      However, settings in the path configuration file could change this location;
      see :doc:`../sysadmin_guide/configuring_sawtooth/path_configuration_file`.

