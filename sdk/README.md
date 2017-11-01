
SDK Examples
========

This tutorial walks through the process of starting the prototype validator and
3 different intkey transaction processors. Also there are two clients to
generate intkey transactions that can be loaded to the transaction processors.

Environment Startup
===================

In order to start the vagrant VM, change the current working directory to
sawtooth-core/tools. If don't you have a vagrant VM running, run:

```
   % cd sawtooth-core/tools
   % vagrant up
   % vagrant ssh
```

After running vagrant ssh you will need to install grpc in the VM:

```
   % cd /project/sawtooth-core/tools/plugins
   % sudo ./install_grpc.sh
```

Now that grpc is installed, the protobuf files need to be generated. The
protogen script generates python classes based on the proto files found in the
protos directory and writes them into
sawtooth-core/sdk/python/sawtooth_sdk.protobuf and
sawtooth-core/validator/sawtooth_validator/protobuf:

```
   % cd /project/sawtooth-core
   % ./bin/protogen
```

Python Intkey Transaction Processors
===================

To run the Intkey Transaction Processor, we need to generate a intkey
transactions file. Run the following command to generate the file
batches.intkey:

```
   % ./bin/intkey create_batch
```

Before we can load the transactions we need to start a validator and a
transaction processor. Run the following to start the validator:

```
   % ./bin/validator
```

In a new terminal, run the following to start the transaction processor:

```
   %cd /project/sawtooth-core
   % ./bin/intkey-tp-python
```

Finally, it is time to load the transactions. In a new terminal, run:

```
   %cd /project/sawtooth-core
   % ./bin/intkey load
```

Java Intkey Transaction Processors
===================

First, java and maven needs to be installed:

```
   % cd /project/sawtooth-core/tools/plugins
   % sudo ./install_jdk.sh
```

Next, the java sdk and java Intkey Transaction Processor needs to be built.
This is done by using maven and a pom.xml file. The sdk pom.xml file is located
at sawtooth-core/sdk/java and and the intkey pom.xml file is located at
sawtooth-core/sdk/examples/intkey_java. To do this, run the following scripts::

```
   % cd /project/sawtooth-core
   % ./bin/build_java_sdk
   % ./bin/build_java_intkey
```

The transactions files need to be generated. Run the following command to
generate the file batches.intkey:

```
   % ./bin/intkey create_batch
```

Before we can load the transactions we need to start a validator and a
transaction processor. Run the following to start the validator:

```
   % ./bin/validator
```

In a new terminal, run the following to start the transaction processor:

```
   %cd /project/sawtooth-core
   % ./bin/intkey-tp-java tcp://localhost:4004
```

Finally, it is time to load the transactions. In a new terminal, run:

```
   %cd /project/sawtooth-core
   % ./bin/intkey load
```
