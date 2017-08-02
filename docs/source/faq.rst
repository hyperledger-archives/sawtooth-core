***
FAQ
***

Validators
==========


How do I change the validator configuration?
--------------------------------------------

An example configuration file is at `sawtooth-core/packaging/validator.toml.example`.
Copy that file to a new file named validator.toml. The new file should be
placed into the config directory declared by path.toml. Edit the validator.toml
file to configure the validator to your needs. When starting sawtooth-validator,
the config file will automatically be found and applied.

Most of the settings in the config file can be overridden on the command line.
