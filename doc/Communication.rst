=================================================================
Communication Layer
=================================================================

The Communication Layer facilitates communication among a collection of
Nodes through gossip protocols. 

Directly connected peers identified by host/port information

Other peers identified by address based on ECDSA verify key

Connection requests must be accepted before packets processed

The Communication Layer provides 

* Rudimentary flow control between peers
* Reliable delivery
* Limited distribution

.. autoclass:: gossip.Gossip.Gossip
   :members: AddNode, DropNode, RegisterMessageHandler,
             ClearMessageHandler, GetMessageHandler, SendMessage,
             ForwardMessage, BroadcastMessage
          
