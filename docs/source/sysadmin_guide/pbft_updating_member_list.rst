****************************************
PBFT Only: Updating the PBFT Member List
****************************************

If you are adding a new node to an existing PBFT network, you must update the
on-chain setting ``sawtooth.consensus.pbft.members`` after the new node has
been installed and configured. This setting takes effect after the containing
block has been committed.

See :ref:`adding-a-pbft-node-label` for this procedure.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
