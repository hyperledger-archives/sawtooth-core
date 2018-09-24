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


Set Up an Apache Proxy Server for the REST API
==============================================

This procedure sets up a simple `Apache 2 <https://httpd.apache.org/>`_ proxy
server that is secured with Basic Auth and https, then configures the proxy
server for an instance of the Sawtooth REST API.

.. note::

   This procedure covers only the information for Sawtooth configuration. It
   does not cover other Apache configuration or security settings.

1. Install the Apache web server and enable the required modules, then restart
   Apache to load these modules.

   .. code-block:: console

      $ sudo apt-get update
      $ sudo apt-get install -y apache2
      $ sudo a2enmod ssl
      $ sudo a2enmod headers
      $ sudo a2enmod proxy_http
      $ sudo systemctl restart apache2

#. Create a password file for the user ``sawtooth``. Enter a new password when
   the ``htpasswd`` command prompts for it.

    .. code-block:: console

       $ sudo htpasswd -c /etc/apache2/.htpassword sawtooth

    .. tip::

       You can repeat this command to generate passwords for other users, but
       you must omit the ``-c`` option from the ``htpasswd`` command. You must
       also remember to authorize those users in the proxy configuration file
       (later in this procedure).

#. Obtain or create an SSL certificate.

   * You can use ``openssl`` to build a self-signed SSL certificate. This
     certificate is not suitable for most HTTP clients, but it is good enough
     for testing purposes.

     .. code-block:: console

        $ sudo mkdir /etc/apache2/keys
        $ sudo openssl req -x509 -nodes -days 7300 -newkey rsa:2048 \
        -subj /C=US/ST=MN/L=Mpls/O=Sawtooth/CN=sawtooth \
        -keyout /etc/apache2/keys/.ssl.key \
        -out /etc/apache2/keys/.ssl.crt

   * You can get a free trusted certificate from
     `Let's Encrypt <https://letsencrypt.org/>`_. Follow the instructions at
     `letsencrypt.org/getting-started <https://letsencrypt.org/getting-started/>`_.

#. Configure the proxy with settings for the Sawtooth REST API.

   a. Create an Apache configuration file.

      .. code-block:: console

         $ sudo vi /etc/apache2/sites-available/000-sawtooth-rest-api.conf

   #. Add the following contents to this file.

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

         Apache automatically sets the "X-Forwarded-Host" header.

   #. Run the following commands to disable the default Apache landing page and
      enable the new authenticated proxy configuration.

      .. code-block:: console

         $ sudo a2dissite 000-default.conf
         $ sudo a2ensite 000-sawtooth-rest-api.conf

   #. Restart Apache to apply the changes.

      .. code-block:: console

         $ sudo systemctl restart apache2

#. Send some test requests to verify the proxy configuration. This step uses
   ``curl`` to send requests to the REST API to make sure that everything works.

   a. Start by querying the REST API directly.

      .. code-block:: console

         $ curl http://localhost:8008/blocks

      The response should look like this example:

      .. code-block:: json

         {
           "link": "http://localhost:8008/blocks?head=..."
         }

      A failed request might mean that the REST API is not running. To restart
      the REST API as a service, see :doc:`systemd`.

   #. Next, query the proxy without authorization. This command should return
      a ``401`` error.

      .. code-block:: console

         $ curl https://localhost/sawtooth/blocks --insecure

      .. note::

         The ``--insecure`` flag forces ``curl`` to complete the request even
         if there isn't an official SSL certificate. It does not bypass
         basic authentication.

   #. Finally, send a properly authorized request. Replace ``{password}`` in the
      following example with the password for the ``sawtooth`` user.

      .. code-block:: console

         $ curl https://localhost/sawtooth/blocks --insecure -u sawtooth:{password}

      The response is similar to a direct query response, but ``link`` shows the
      URL used to send this request.

      .. code-block:: json

         {
           "link": "https://localhost/sawtooth/blocks?head=..."
         }


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
