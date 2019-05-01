* :term:`PBFT consensus` provides a voting-based consensus algorithm with
  Byzantine fault tolerance (BFT) that has finality (does not fork).

* :term:`PoET consensus` provides a leader-election lottery system that can
  fork.  This network uses PoET simulator consensus, which is also called `PoET
  CFT` because it is crash fault tolerant.

  .. note::

     The other type of PoET consensus, PoET-SGX, relies on Intel Software Guard
     Extensions (SGX) that is Byzantine fault tolerant (BFT). PoET CFT provides
     the same consensus algorithm on an SGX simulator.

