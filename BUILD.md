
![Hyperledger Sawtooth](images/sawtooth_logo_light_blue-small.png)

Hyperledger Sawtooth Core Developer's Setup Guide
=============
If you are planning to contribute code to the Sawtooth project please review the contributing guide: [CONTRIBUTING.md]

Supported Operating Systems: Ubuntu 16.04 and MacOS

If you are planning to develop or contribute from a computer running a windows
operating system, we recommend that you install Ubuntu 16.04 in a virtual
machine manager, such as Hyper-V or VirtualBox, and develop from the guest os(or "Ubuntu OS").

**Note:** All commands in this guide use the Bash shell. While the bash shell is not strictly required as the command shell, many of the scripts in the build system are Bash scripts and require Bash to execute.

Step One: Install Docker
-------------
The Sawtooth Core Requirements are:
- Docker Community Edition ( 17.05.0-ce or newer)
- Docker compose (version 1.13.0 or newer)

macOS
=============

Install the latest version of Docker Engine for macOS:
https://docs.docker.com/docker-for-mac/install/

On macOS Docker Compose is installed automatically when you
install Docker Engine.

Linux
=============

Install the latest version of Docker Engine for Linux:

- Install Docker Engine: <https://docs.docker.com/engine/installation/linux/>ubuntu
- Install Docker Compose: <https://docs.docker.com/compose/install/>

**Note:** that the minimum version of Docker Engine necessary is 17.03.0-ce.
  Linux distributions often ship with older versions of Docker.

**Note:** Add your username to the group `docker` to avoid having to run every
docker command as a `sudo`. If you do not do this you will need to prefix all
the commands in section Four, Five, and Six with `sudo`. To add your username
to the docker group, run the following command:
```bash
$ sudo adduser $USER docker
```
if $USER is not set in the environment on your system, replace $USER in the previous command with your username.

Afterwards you will need to log out and log back in to your system for the change in group membership to take effect.

Step Two: Configure Proxy (Optional)
-------------

If you are behind a network proxy, follow these steps before continuing:

Set the following environment variables:
  - http_proxy
  - https_proxy
  - no_proxy

Run the following commands:

**Warning:** The example URLs and port numbers used below are examples only.
Please substitute the actual URL, with actual port numbers, used in your
environment. Contact your network administrator for the information if
necessary.

```bash
  $ export http_proxy=http://proxy-server.example:3128
  $ export https_proxy=http://proxy-server.example:3129
  $ export no_proxy=example.com,another-example.com,127.0.0.0
```

**Note:** You will want to add these to either your .profile or .bashrc file
so you don't have to reset them everytime you open a new shell.

**Docker Proxy Settings (Optional)**

To configure Docker to work with an HTTP or HTTPS proxy server, follow the
instructions for your operating system:

* macOS - See the instructions for proxy configuration in
Get Started with Docker for Mac: <https://docs.docker.com/docker-for-mac/>

* Linux - See the instructions for proxy configuration in
Control and configure Docker with Systemd: <https://docs.docker.com/engine/admin/systemd/#httphttps-proxy>

Create a file `/etc/systemd/system/docker.service.d/http-proxy.conf` with the
contents:

**Warning:** The example URLs and port numbers used below are examples only.
Please substitute the actual URL, with actual port numbers, used in your
environment. Contact your network administrator for the information if
necessary.

```text
[Service]
Environment="HTTP_PROXY=http://proxy-server.example:3128" "HTTPS_PROXY=http://proxy-server.example:3129" "http_proxy=http://proxy-server.example:3128" "https_proxy=http://proxy-server.example:3129" "no_proxy=example.com,another-example.com,127.0.0.0"
```

Restart docker
```bash
$ sudo systemctl daemon-reload
$ sudo systemctl restart docker
```

Verify that the configuration has been loaded:
```bash
$ systemctl show --property=Environment docker
Environment=HTTP_PROXY=http://proxy-server.example:80/
```

**Docker DNS (Optional)**

Docker build uses /etc/resolv.conf for setting up DNS servers for docker image
builds. If you are receiving `Host not found` errors during docker build steps
then you will need to add nameserver entries to the resolve.conf file. Since
the resolv.conf file is automaticly generated on Ubuntu you will need to
install a configuration utility.

```bash
sudo apt-get install resolvconf
```

Edit the /etc/resolvconf/resolv.conf.d/base as root and add the dns servers
for your network. If you are behind a firewill you may have specific servers
for your network that need to be used.

For example to use Google's public DNS servers:
```
    nameserver 8.8.8.8
    nameserver 8.8.4.4
```



Step Three: Clone The Repository
-------------

You'll need to have git installed in order to clone the Sawtooth source
code repository. You can find up-to-date installation instructions
at Getting Started - Installing Git: <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>.

Open up a terminal and run the following:

```bash
   $ cd $HOME
   $ mkdir sawtooth
   $ cd sawtooth
   $ git clone https://github.com/hyperledger/sawtooth-core.git
```

Step Four: Initializing Your Environment
-------------

The Sawtooth build and test infrastructure requires dependencies be built.
These dependencies include the protocol buffers definitions (under the protos
dir) be built for the target languages and a set of docker images be built with
the required build and runtime dependencies installed.  To build all the
dependencies for all of the components of Sawtooth, run this command:

```bash
  $ bin/build_all
```

By default, this builds all the components for all the components and sdks in
the repository. This is a very slow process. It is recommended that you only
build the language dependencies you need for your development purposes. The
minimum requirements for running the Sawtooth validator is the python build:

```bash
  $ bin/build_all -l python
```

To get details on all the options for the build_all script

```bash
  $ bin/build_all -h
```

If you are working on the core validator, only the ‘python’ language is
required. If you are working on a particular language sdk then you will need to
build the language that sdk is for as well.

**Note:** This build environment uses docker to virtualize the build and
execute the code in the development directory. This allows for modification
made to the local source to be built and tested without installing local
dependencies on your machine.

If you wish to configure your development machine to do compilation
directly on the host without docker virtualization, see the docker files in the
sawtooth-core/docker directory. For example, the file sawtooth-core/docker
sawtooth-dev-python describes the configuration and components needed to build
and run the python components on a system.

Step Five: Development Tasks
-------------

To run a full Validator Node from the local source:

```bash
  $ docker-compose -f docker/compose/sawtooth-local.yaml up
```

This will start a validator with the following components attached to it:
  - Xo Transaction Processor ( python implementation )
  - IntKey Transaction Processor ( python implementation )
  - Settings Transaction Processor
  - REST API - available on host port 8008
  - Shell - for running sawtooth cli commands

From another console window you can access the shell
```bash
  $ docker-compose -f docker/compose/sawtooth-local.yaml exec client bash
```

This command uses Docker Compose and the development docker images. These
docker images have the runtime dependencies installed in them but run sawtooth
from the source in your workspace. Inspecting
`docker/compose/sawtooth-local.yaml` will show how the various components are
launched and connected.

Step Six: Running Tests
-------------

The automated tests for python and all other languages rely on docker to
ensure reproducibility. To run the automated tests for python, you will first
need to build the the docker images using the `build_all` command described in
Step Three: Initializing Your Environment.

You can then run the automated tests for python components, while excluding
java, javascript, go and rust components, with:

```bash
  $ bin/run_tests -x java_sdk -x javascript_sdk -x go_sdk -x rust_sdk
```

**Note:** The `run_tests` command provides the -x flag to allow you to exclude
various components from tests. You can also specify which tests to run
with the -m flag. Run the command `run_tests -h` for help.
