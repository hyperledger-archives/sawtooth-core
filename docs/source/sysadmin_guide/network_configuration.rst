*********************
Network Configuration
*********************

Validators
==========

Sawtooth Lake uses two ports, one TCP, one UDP, to communicate with other 
members of a validator network. You may need to modify some firewall rules
to facilitate this traffic. Because the validator software assumes complete
connectivity to the other nodes in the network, if you intend to participate
in a Sawtooth Lake network over the internet, each validator will need a
publically routable IP address. NAT is not currently supported.

Primarily, traffic between validator nodes takes place over UDP. By default
Sawtooth Lake selects a random high UDP port for communication. You can choose
a static port to use by changing the "Port" value from "0" to any unused UDP
port. We recommend using 5500. Your firewall rules should be configured to
allow both ingress and egress from all networks for this port.

The validator nodes listen on TCP port 8800 for communication from clients.
This port is adjustable via the config file value "HttpPort", though changing
this requires additional client configuration. Firewall rules should be
configured to allow both ingress and egress from all networks for this port.

Required Validator ports:

* UDP/5500: ingress and egress
* TCP/8800: ingress and egress

These values are configurable by editing
``/etc/sawtooth-validator/txnvalidator.js`` on Linux or
``C:\Program Files(x86)\Intel\sawtooth-validator\conf\txnvalidator.js`` on
Windows.


Clients
=======

The Sawtooth Lake client communicates with validators via TCP port 8800.
Firewall rules should be adjusted to allow egress traffic on port 8800
from each machine running the Sawtooth Lake client software to each validator
you will be working with. If you've altered the "HttpPort" value of your
validator's configuration file, this port will need to be allowed instead
of the default 8800.

Required Client ports:

* TCP/8800: egress
