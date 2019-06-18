
.. _about-bind-strings-label:

About component and network bind strings
""""""""""""""""""""""""""""""""""""""""

For the network bind string and component bind string, you would typically use
a specific network interface that you want to bind to.
The ``ifconfig`` command provides an easy way to determine what this interface
should be. ``ifconfig`` displays the network interfaces on your host system,
along with additional information about the interfaces. For example:

.. code-block:: console

   $ ifconfig
   eth0      Link encap:Ethernet  HWaddr ...
             inet addr:...  Bcast:...  Mask:255.255.0.0
             UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
             RX packets:17964 errors:0 dropped:0 overruns:0 frame:0
             TX packets:6134 errors:0 dropped:0 overruns:0 carrier:0
             collisions:0 txqueuelen:0
             RX bytes:26335425 (26.3 MB)  TX bytes:338394 (338.3 KB)
   lo        Link encap:Local Loopback
             inet addr:127.0.0.1  Mask:255.0.0.0
             UP LOOPBACK RUNNING  MTU:65536  Metric:1
             RX packets:0 errors:0 dropped:0 overruns:0 frame:0
             TX packets:0 errors:0 dropped:0 overruns:0 carrier:0
             collisions:0 txqueuelen:1
             RX bytes:0 (0.0 B)  TX bytes:0 (0.0 B)

This example output shows that ``eth0`` is a network interface that has access
to the Internet. In this case, you could use one of the following:

* If you would like the validator to accept connections from other
  nodes on the network behind ``eth0``, you could specify a
  network bind string such as ``tcp://eth0:8800``.

* If you would like the validator to accept only connections from local
  Sawtooth components, you could specify the component bind string
  ``tcp://lo:4004``. Note that this is equivalent to ``tcp://127.0.0.1:4004``.

For more information on how to specify the component and network bind strings,
see "Assigning a local address to a socket" in the
`zmq-tcp API Reference <http://api.zeromq.org/4-2:zmq-tcp>`_.

.. _about-endpoint-string-label:

About the public endpoint string
""""""""""""""""""""""""""""""""

The correct value for your public endpoint string depends on your network
configuration.

* If this network is for development purposes and all of the nodes
  will be on the same local network, the IP address returned by ``ifconfig``
  should work as your public endpoint string.

* If part of your network is behind a NAT or firewall, or if you want to start
  up a public network on the Internet, you must determine the correct routable
  values for all the nodes in your network.

  Determining these values for a distributed or production network is an
  advanced networking topic that is beyond the scope of this guide. Contact your
  network administrator for help with this task.

For information on how to specify the public endpoint string, see "Connecting
a socket" in the `zmq-tcp API Reference <http://api.zeromq.org/4-2:zmq-tcp>`_.

