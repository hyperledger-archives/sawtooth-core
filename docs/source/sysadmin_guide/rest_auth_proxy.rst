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

We'll begin by installing the Apache webserver and enabling the required
modules. Apache will need to be restarted for these modules to load.

.. code-block:: console

   $ sudo apt-get update
   $ sudo apt-get install -y apache2
   $ sudo a2enmod ssl
   $ sudo a2enmod headers
   $ sudo a2enmod proxy_http
   $ sudo systemctl restart apache2


Set Up Passwords and Certificates
---------------------------------

First we'll create a password file for the user *"sawtooth"*. Enter your
desired password when the ``htpasswd`` command prompts for it. You can generate
a password for other users as well, just make sure to remove the ``-c`` from
the ``htpasswd`` command and authorize those users in the apache config file
as shown in the section below.

.. code-block:: console

   $ sudo htpasswd -c /etc/apache2/.htpassword sawtooth

Then we'll use ``openssl`` to build a self-signed SSL certificate. This
certificate will not be good enough for most HTTP clients, but is suitable for
testing purposes.

.. code-block:: console

   $ sudo mkdir /etc/apache2/keys
   $ sudo openssl req -x509 -nodes -days 7300 -newkey rsa:2048 \
       -subj /C=US/ST=MN/L=Mpls/O=Sawtooth/CN=sawtooth \
       -keyout /etc/apache2/keys/.ssl.key \
       -out /etc/apache2/keys/.ssl.crt


.. note::

   Let's Encrypt provides a trusted certificate at no cost. Follow the
   instructions at Let's Encrypt <https://letsencrypt.org/>_.


Configure Proxy
---------------

Now we'll set up the proxy by creating an Apache config file.

.. code-block:: console

   $ sudo vi /etc/apache2/sites-available/000-sawtooth-rest-api.conf

Edit the file to look like this:

.. code-block:: apache

   <VirtualHost *:443>
       ServerName sawtooth
       ServerAdmin sawtooth@sawtooth
       DocumentRoot /var/www/html

       SSLEngine on
       SSLCertificateFile /etc/apache2/keys/.ssl.crt
       SSLCertificateKeyFile /etc/apache2/keys/.ssl.key
       RequestHeader set X-Forwarded-Proto "https"

       <Location />
           Options Indexes FollowSymLinks
           AllowOverride None
           AuthType Basic
           AuthName "Enter password"
           AuthUserFile "/etc/apache2/.htpassword"
           Require user sawtooth
           Require all denied
       </Location>
   </VirtualHost>

   ProxyPass /sawtooth http://localhost:8008
   ProxyPassReverse /sawtooth http://localhost:8008
   RequestHeader set X-Forwarded-Path "/sawtooth"

.. note::

   Apache will automatically set the *X-Forwarded-Host* header.


Disable the default Apache landing page and enable our new authenticated proxy
config.

.. code-block:: console

   $ sudo a2dissite 000-default.conf
   $ sudo a2ensite 000-sawtooth-rest-api.conf


Restart Apache
--------------

Restart Apache to apply our changes.

.. code-block:: console

   $ sudo systemctl restart apache2


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

   $ curl https://localhost/sawtooth/blocks --insecure -u sawtooth:{password}

.. note::

   Change ``{password}`` here to match the one used in the ``htpasswd`` command
   above.

We should get back a response that looks very similar to querying the REST API
directly, but with a new *link* that reflects the URL we sent the request to:

.. code-block:: json

   {
     "link": "https://localhost/sawtooth/blocks?head=..."
   }

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
