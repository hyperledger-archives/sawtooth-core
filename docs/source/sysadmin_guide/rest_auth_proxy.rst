**********************************************
Using a Proxy Server to Authorize the REST API
**********************************************

As a lightweight shim on top of internal communications, requests sent to the
*Hyperledger Sawtooth* REST API are simply passed on to the validator, without
any sort of authorization. While this is in keeping with the public nature of
blockchains, that behavior may not be desirable in every use case. Rather than
internally implementing one authorization scheme or another, the REST API is
designed to work well behind a proxy server, allowing any available
authorization scheme to be implemented externally.


Forwarding URL Info with Headers
================================

For the most part putting the REST API behind a proxy server should just work.
The majority of what it does will work equally well whether or not it is
communicating directly with a client. The notable exceptions being the `"link"`
parameter sent back in the response envelope, and the `"previous"` and `"next"`
links that are sent back with a paging response. These URLs can be a
convenience for clients, but not when crucial URL information is destroyed by
proxying. In that case, a link that should look like this:

.. code-block:: json

   {
     "link": "https://hyperledger.org/sawtooth/blocks?head=..."
   }

Might instead look like this:

.. code-block:: json

   {
     "link": "http://localhost:8008/blocks?head=..."
   }

The solution to this problem is sending the destroyed information using HTTP
request headers. The Sawtooth REST API will properly recognize and parse two
sorts of headers.


"X-Forwarded" Headers
---------------------

Although they aren't part of any standard, the various *X-Forwarded* headers
are a very common way of communicating useful information about a proxy. There
are three of these headers that the REST API may look for when building links.

.. list-table::
   :widths: 20, 44, 16
   :header-rows: 1

   * - header
     - description
     - example
   * - **X-Forwarded-Host**
     - The domain name of the proxy server.
     - *hyperledger.org*
   * - **X-Forwarded-Proto**
     - The protocol/scheme used to make request.
     - *https*
   * - **X-Forwarded-Path**
     - An uncommon header implemented specially by the REST API to handle extra
       path information. Only necessary if the proxy endpoints do not map
       directly to the REST API endpoints (i.e.
       *"hyperledger.org/sawtooth/blocks"* -> *"localhost:8008/blocks"*).
     - */sawtooth*


"Forwarded" Header
------------------

Although less common, the same information can be sent using a single
*Forwarded* header, standardized by
`RFC7239 <https://tools.ietf.org/html/rfc7239#section-4>`_. The Forwarded
header contains semi-colon-separated key value pairs. It might for example look
like this:

.. code-block:: text

   Forwarded: for=196.168.1.1; host=proxy1.com, host=proxy2.com; proto="https"

There are three keys in particular the REST API will look for when building
response links:

.. list-table::
   :widths: 8, 52, 20
   :header-rows: 1

   * - key
     - description
     - example
   * - **host**
     - The domain name of the proxy server.
     - *host=hyperledger.org*
   * - **proto**
     - The protocol/scheme used to make request.
     - *proto=https*
   * - **path**
     - An non-standard key header used to handle extra path information. Only
       necessary if the proxy endpoints do not map directly to the REST API
       endpoints (i.e. *"hyperledger.org/sawtooth/blocks"* ->
       *"localhost:8008/blocks"*).
     - *path="/sawtooth"*

.. note::

   Any key in a *Forwarded* header can be set multiple times, each instance
   comma-separated, allowing for a chain of proxy information to be traced.
   However, the REST API will always reference the leftmost of any particular
   key. It is only interested in producing an accurate link for the original
   client.


Apache Proxy Setup Guide
========================

For further clarification, this section walks through the setup of a simple
`Apache 2 <https://httpd.apache.org/>`_ proxy server secured with Basic Auth
and https, pointed at an instance of the *Sawtooth* REST API.


Install Apache
--------------

We'll begin by installing Apache and its components. These commands may require
``sudo``.

.. code-block:: console

   $ apt-get update
   $ apt-get install -y apache2
   $ a2enmod ssl
   $ a2enmod headers
   $ a2enmod proxy_http


Set Up Passwords and Certificates
---------------------------------

First we'll create a password file for the user *"sawtooth"*, with the password
*"sawtooth"*. You can
`generate other .htpasswd files <http://www.htaccesstools.com/htpasswd-generator/>`_
as well, just make sure to authorize those users in the config file below.

.. code-block:: console

   $ echo "sawtooth:\$apr1\$cyAIkitu\$Cv6M2hHJlNgnVvKbUdlFr." >/tmp/.password

Then we'll use ``openssl`` to build a self-signed SSL certificate. This
certificate will not be good enough for most HTTP clients, but is suitable for
testing purposes.

.. code-block:: console

   $ openssl req -x509 -nodes -days 7300 -newkey rsa:2048 \
       -subj /C=US/ST=MN/L=Mpls/O=Sawtooth/CN=sawtooth \
       -keyout /tmp/.ssl.key \
       -out /tmp/.ssl.crt


Configure Proxy
---------------

Now we'll set up the proxy by editing an Apache config files. This may require
``sudo``.

.. code-block:: console

   $ vi /etc/apache2/sites-enabled/000-default.conf

Edit the file to look like this:

.. code-block:: apache

   <VirtualHost *:443>
       ServerName sawtooth
       ServerAdmin sawtooth@sawtooth
       DocumentRoot /var/www/html

       SSLEngine on
       SSLCertificateFile /tmp/.ssl.crt
       SSLCertificateKeyFile /tmp/.ssl.key
       RequestHeader set X-Forwarded-Proto "https"

       <Location />
           Options Indexes FollowSymLinks
           AllowOverride None
           AuthType Basic
           AuthName "Enter password"
           AuthUserFile "/tmp/.password"
           Require user sawtooth
           Require all denied
       </Location>
   </VirtualHost>

   ProxyPass /sawtooth http://localhost:8008
   ProxyPassReverse /sawtooth http://localhost:8008
   RequestHeader set X-Forwarded-Path "/sawtooth"

.. note::

   Apache will automatically set the *X-Forwarded-Host* header.


Start Apache, a Validator, and the REST API
-------------------------------------------

Start or restart Apache as appropriate. This may require ``sudo``.

.. code-block:: console

   $ apachectl start

.. code-block:: console

   $ apachectl restart


Start a validator, and the REST API.

.. code-block:: console

   $ sawadm keygen
   $ sawadm genesis
   $ sawtooth-validator -v --endpoint localhost:8800
   $ sawtooth-rest-api -v


Send Test Requests
------------------

Finally, let's use ``curl`` to make some requests and make sure everything
worked. We'll start by querying the REST API directly:

.. code-block:: console

   $ curl http://localhost:8008/blocks

The response link should look like this:

.. code-block:: json

   {
     "link": "http://localhost:8008/blocks?head=..."
   }

You should also be able to get back a ``401`` by querying the proxy without
authorization:

.. code-block:: console

   $ curl https://localhost/sawtooth/blocks --insecure

.. note::

   The ``--insecure`` flag just forces curl to complete the request even though
   there isn't an official SSL Certificate. It does *not* bypass Basic Auth.

And finally, if we send a properly authorized request:

.. code-block:: console

   $ curl https://localhost/sawtooth/blocks --insecure -u sawtooth:sawtooth

We should get back a response that looks very similar to querying the REST API
directly, but with a new *link* that reflects the URL we sent the request to:

.. code-block:: json

   {
     "link": "https://localhost/sawtooth/blocks?head=..."
   }

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
