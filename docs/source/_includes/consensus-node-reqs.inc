  - :term:`PBFT consensus` requires four or more nodes. At least four nodes must
    be configured and running in order for the network to start.

  - :term:`PoET consensus` requires three or more nodes. You can start the first
    node and test basic functionality, then add the other nodes.

    .. note::

       This procedure uses PoET simulator consensus (also called PoET CFT
       because it is crash fault tolerant), which is a version of PoET-SGX
       consensus that runs on any processor.

  - :term:`Devmode consensus` has no minimum requirement,
    but it is not recommended for multiple-node test networks or production
    networks. Devmode is a light-weight consensus that is intended for
    short-term testing on a single node or a very small network (two or three
    nodes). It is not crash fault tolerant and does not handle forks
    efficiently.

