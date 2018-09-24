**********************************************
Using a Proxy Server to Authorize the REST API
**********************************************

The Sawtooth REST API is designed to be a lightweight shim on top of internal
communications. When the REST API receives a request, it passes that request to
the validator without any authorization. While this behavior is appropriate for
the public nature of blockchains, the lack of authorization might not be
desirable in some situations. For these cases, you can configure the REST API to
work behind a proxy server.

This section explains how the REST API handles proxy server issues, then shows
how to set up an Apache proxy server for the REST API.


About Proxying the REST API
===========================

In general, putting the REST API behind a proxy server works as expected. The
REST API has the same behavior as if it were communicating directly with a
client. The notable exception is how URLs are handled; specifically, the
``link`` parameter that is sent back in the response envelope, and the
``previous`` and ``next`` links that are sent back with a paging response.

These URLs are a convenience for clients, but the proxy can destroy crucial URL
information.  For example, a correct link should look this this:

.. code-block:: json

   {
     "link": "https://hyperledger.org/sawtooth/blocks?head=..."
   }

Instead, the "destroyed" link might look like this:

.. code-block:: json

   {
     "link": "http://localhost:8008/blocks?head=..."
   }

The solution to this problem is to send the destroyed information with HTTP
request headers. The Sawtooth REST API will properly recognize and parse
information in both "X-Forwarded" and "Forwarded" headers.

"X-Forwarded" Headers
---------------------

Although they aren't part of any standard, "X-Forwarded" headers are a common
way to communicate information about a proxy. When the REST API builds a link,
it looks for the following types of "X-Forwarded" headers:

* ``X-Forwarded-Host``:
  Domain name of the proxy server (for example, ``hyperledger.org``)

* ``X-Forwarded-Proto``:
  Protocol/scheme used to make requests (for example, ``https``)

* ``X-Forwarded-Path``:
  Extra path information (for example, ``/sawtooth``). This uncommon header is
  implemented by the REST API. It is necessary only if the proxy endpoints do
  not map directly to the REST API endpoints, that is, when
  ``hyperledger.org/sawtooth/blocks`` does not map to ``localhost:8008/blocks``.

"Forwarded" Headers
-------------------

This type of header is less common, but a single "Forwarded" header sends the
same information as multiple "X-Forwarded" headers.  The "Forwarded" header,
which is standardized by
`RFC7239 <https://tools.ietf.org/html/rfc7239#section-4>`_, contains
semicolon-separated key-value pairs, as in this example:

.. code-block:: text

   Forwarded: for=196.168.1.1; host=proxy1.com, host=proxy2.com; proto="https"

When the REST API builds a response link, it looks for the following keys:

* ``host``:
  Domain name of the proxy server (for example, ``host=hyperledger.org``)

* ``proto``:
  Protocol/scheme used to make requests (for example, ``proto=https``)

* ``path``:
  Extra path information (for example, ``path="/sawtooth"``). This non-standard
  key header is necessary only if the proxy endpoints do not map directly to
  the REST API endpoints, that is, when ``hyperledger.org/sawtooth/blocks`` does
  not map to ``localhost:8008/blocks``.

.. note::

   Any key in a "Forwarded" header can be set multiple times, using commas to
   separate each setting. (See the ``host`` values in the example above.)
   Repeating a key allows a chain of proxy information to be traced. However,
   the REST API always uses the left-most value for a particular key so that it
   can produce an accurate link for the client.


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
